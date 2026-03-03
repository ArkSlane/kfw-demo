"""
Locator scanner — AI-assisted data-testid insertion and extraction.

Two core capabilities:
  1. update_code_with_locators  – send source code to an LLM which returns the
     entire file with data-testid attributes added to interactive elements.
  2. extract_locators_from_code – parse HTML/JSX and pull out every data-testid
     along with its opening-tag markup.

All LLM calls go through the Ollama HTTP API (no pip ``ollama`` package needed)
so this module works inside the existing async FastAPI service.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import PurePosixPath

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic model for structured LLM response
# ---------------------------------------------------------------------------

class CodeResponse(BaseModel):
    code: str
    message: str


# ---------------------------------------------------------------------------
# 1. Ask the LLM to add data-testid attributes
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # seconds, doubled each retry


async def update_code_with_locators(
    code: str,
    file_name: str,
    *,
    ollama_url: str,
    ollama_model: str,
) -> CodeResponse:
    """Send *code* to Ollama and get back the full file with ``data-testid``
    attributes inserted on interactive / important elements.

    The prompt instructs the model to:
    * Never remove existing lines – only *add* ``data-testid`` attributes.
    * Prefix every locator name with *file_name* for uniqueness.
    * Return valid JSON matching :class:`CodeResponse`.

    Retries up to *_MAX_RETRIES* times on empty / unparseable responses and
    transient connection errors.
    """
    prompt = (
        "You are a test automation assistant.\n"
        "YOU MUST ALWAYS RETURN THE FULL CODE AND ONLY THE FULL CODE.\n"
        "YOU NEVER DELETE LINES OF CODE AND ONLY ADD data-testid attributes.\n"
        "Your task is to analyze the code and add locators using data-testid to "
        "the interactive and important elements in the code.\n\n"
        "Please ensure that the locators are unique and meaningful. "
        f'Prepend the locator names with the filename: "{file_name}". '
        f'Example: filename = "{file_name}" → locatorname = "{file_name}-submit-btn".\n\n'
        "The code is from a single file. You should return the whole code with "
        "the added locators.\n\n"
        "You MUST respond with ONLY a JSON object (no markdown, no explanation outside the JSON) "
        "with exactly two keys:\n"
        '  "code": the full updated source code as a single string,\n'
        '  "message": a short summary of what you changed.\n\n'
        "Example response format:\n"
        '{"code": "<full source code with data-testid added>", "message": "Added 3 data-testid attributes"}\n\n'
        "Here is the code:\n\n"
        + code
    )

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0,
        "top_p": 1,
    }

    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json=payload,
                    timeout=300,
                )
                resp.raise_for_status()
                body = resp.json()
                raw = (body.get("response") or "").strip()

            if not raw:
                logger.warning(
                    "Ollama returned empty response for %s (attempt %d/%d)",
                    file_name, attempt + 1, _MAX_RETRIES,
                )
                last_error = ValueError(
                    f"Ollama returned an empty response for {file_name}"
                )
                await _backoff(attempt)
                continue

            logger.info(
                "Ollama responded for %s (attempt %d/%d, %d chars)",
                file_name, attempt + 1, _MAX_RETRIES, len(raw),
            )
            return _parse_code_response(raw)

        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            logger.warning(
                "Ollama connection issue for %s (attempt %d/%d): %s",
                file_name, attempt + 1, _MAX_RETRIES, exc,
            )
            last_error = exc
            await _backoff(attempt)
            continue

        except Exception as exc:
            logger.warning(
                "Ollama response parse error for %s (attempt %d/%d): %s  raw[:200]=%s",
                file_name, attempt + 1, _MAX_RETRIES, exc,
                repr(raw[:200]) if 'raw' in dir() else "N/A",
            )
            last_error = exc
            await _backoff(attempt)
            continue

    raise last_error or RuntimeError(f"Failed to get locators for {file_name}")


async def _backoff(attempt: int) -> None:
    """Async exponential back-off."""
    await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))


def _parse_code_response(raw: str) -> CodeResponse:
    """Try to parse *raw* as a :class:`CodeResponse` JSON string.

    The model may return:
    1. Clean JSON: {"code": "...", "message": "..."}
    2. JSON wrapped in markdown fences: ```json\n{...}\n```
    3. Prose before/after the JSON block
    4. Raw code in markdown fences (no JSON wrapper at all)
    5. Raw code with no fences
    We handle all cases.
    """
    # --- Attempt 1: direct parse ---
    try:
        return CodeResponse.model_validate_json(raw)
    except Exception:
        pass

    # --- Attempt 2: find JSON inside markdown fences ---
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence_match:
        inside_fence = fence_match.group(1).strip()
        try:
            return CodeResponse.model_validate_json(inside_fence)
        except Exception:
            pass

    # --- Attempt 3: find the outermost { ... } that parses as CodeResponse ---
    # We look for `"code"` key to avoid matching random braces in source code
    json_match = re.search(r'\{\s*"code"\s*:', raw)
    if json_match:
        brace_start = json_match.start()
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[brace_start : i + 1]
                    try:
                        return CodeResponse.model_validate_json(candidate)
                    except Exception:
                        pass
                    break

    # --- Attempt 4: model returned raw code (not JSON) ---
    # Extract code from markdown fences and wrap it ourselves
    code_fence_match = re.search(
        r"```(?:tsx|jsx|html|vue|svelte|ts|js)?\s*\n(.*?)```",
        raw,
        re.DOTALL,
    )
    if code_fence_match:
        extracted_code = code_fence_match.group(1).strip()
        if extracted_code:
            logger.info(
                "Model returned raw code in markdown fences (%d chars) — wrapping as CodeResponse",
                len(extracted_code),
            )
            return CodeResponse(
                code=extracted_code,
                message="Added data-testid attributes (extracted from raw response)",
            )

    # --- Attempt 5: no fences at all, but the response looks like code ---
    # If it starts with an import/export/function or HTML tag, treat the whole thing as code
    stripped = raw.strip()
    if stripped and (
        stripped.startswith(("import ", "export ", "function ", "const ", "let ", "var ", "<"))
        or re.match(r"^(import|export|function|const|let|var|<[a-zA-Z])", stripped)
    ):
        logger.info(
            "Model returned raw code without fences (%d chars) — wrapping as CodeResponse",
            len(stripped),
        )
        return CodeResponse(
            code=stripped,
            message="Added data-testid attributes (extracted from raw response)",
        )

    raise ValueError(
        f"Could not parse CodeResponse from Ollama output ({len(raw)} chars). "
        f"First 300 chars: {raw[:300]!r}"
    )


# ---------------------------------------------------------------------------
# 2. Extract existing data-testid locators from markup
# ---------------------------------------------------------------------------

def extract_locators_from_code(code: str) -> list[dict[str, str]]:
    """Parse *code* with BeautifulSoup and return every ``data-testid``
    together with its opening-tag markup.

    Returns a list of ``{"locator": "<testid>", "element": "<tag ...>"}``
    dicts.  Duplicates (by testid value) are skipped.
    """
    soup = BeautifulSoup(code, "html.parser")
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for tag in soup.find_all(attrs={"data-testid": True}):
        loc = tag.get("data-testid")
        if not loc or loc in seen:
            continue
        seen.add(loc)
        attrs_str = " ".join(
            f'{key}="{val}"' if isinstance(val, str) else f'{key}="{" ".join(val)}"'
            for key, val in tag.attrs.items()
        )
        element_str = f"<{tag.name} {attrs_str}>"
        results.append({"locator": loc, "element": element_str})
    return results
