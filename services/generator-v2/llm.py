"""
LangChain LLM integration — Azure AI Foundry (Azure OpenAI) backend.

Provides:
  - `get_llm()` — returns a configured AzureChatOpenAI instance
  - `llm_generate(prompt, timeout)` — simple text generation
  - `llm_generate_json(prompt, timeout)` — generation with JSON mode
  - `llm_generate_structured(prompt, schema, timeout)` — structured output via Pydantic model
"""

import os
import json
import logging
from typing import Type, TypeVar

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Azure AI Foundry Configuration ──────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8192"))

# Backward-compatible alias used in response metadata across services
LLM_MODEL = AZURE_OPENAI_DEPLOYMENT

T = TypeVar("T", bound=BaseModel)

_llm_instance = None
_llm_json_instance = None


def get_llm(response_format: dict | None = None, timeout: int = 90) -> AzureChatOpenAI:
    """Get a configured AzureChatOpenAI instance."""
    kwargs = dict(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT,
        temperature=LLM_TEMPERATURE,
        top_p=LLM_TOP_P,
        max_tokens=LLM_MAX_TOKENS,
        timeout=timeout,
    )
    if response_format:
        kwargs["model_kwargs"] = {"response_format": response_format}
    return AzureChatOpenAI(**kwargs)


def get_llm_cached() -> AzureChatOpenAI:
    """Get a cached AzureChatOpenAI instance for text generation."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm()
    return _llm_instance


def get_llm_json_cached() -> AzureChatOpenAI:
    """Get a cached AzureChatOpenAI instance with JSON mode."""
    global _llm_json_instance
    if _llm_json_instance is None:
        _llm_json_instance = get_llm(response_format={"type": "json_object"})
    return _llm_json_instance


async def llm_generate(prompt: str, *, system: str = "", timeout: int = 90) -> str:
    """Simple text generation — returns the raw response string."""
    llm = get_llm(timeout=timeout)
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    response = await llm.ainvoke(messages)
    return response.content


async def llm_generate_with_usage(prompt: str, *, system: str = "", timeout: int = 90) -> tuple[str, dict]:
    """Text generation that also returns token usage.

    Returns (content, usage_dict) where usage_dict has
    prompt_tokens, completion_tokens, total_tokens.
    """
    llm = get_llm(timeout=timeout)
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    response = await llm.ainvoke(messages)
    usage = (response.response_metadata or {}).get("token_usage") or {}
    if not usage:
        usage = (response.response_metadata or {}).get("usage") or {}
    return response.content, {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


async def llm_generate_json(prompt: str, *, system: str = "", timeout: int = 90) -> dict:
    """Generate with JSON mode — returns parsed dict."""
    llm = get_llm(response_format={"type": "json_object"}, timeout=timeout)
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    response = await llm.ainvoke(messages)
    text = response.content.strip()
    return json.loads(text)


async def llm_generate_structured(
    prompt: str,
    schema: Type[T],
    *,
    system: str = "",
    timeout: int = 90,
    retries: int = 3,
) -> T:
    """Generate structured output validated against a Pydantic model.

    Uses JSON mode + manual parsing with retry logic.
    """
    llm = get_llm(response_format={"type": "json_object"}, timeout=timeout)

    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = await llm.ainvoke(messages)
            text = response.content.strip()
            parsed = json.loads(text)
            return schema.model_validate(parsed)
        except Exception as e:
            last_error = e
            logger.warning(f"Structured output attempt {attempt} failed: {e}")
            # Add error feedback for retry
            if attempt < retries:
                messages.append(HumanMessage(
                    content=f"Your output did not validate. Error: {e}. Return corrected JSON matching the schema exactly."
                ))

    raise last_error
