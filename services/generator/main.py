import os
import json
from datetime import datetime, timezone
from typing import Literal
import re
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator
import httpx
import asyncio
from shared.models import GenerateRequest, GenerateResult, TestcaseOut
from shared.errors import setup_all_error_handlers
from shared.health import check_ollama, check_playwright_mcp, check_http_service, aggregate_health_status
from git_integration import push_test_to_git, trigger_test_execution

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT_URL")
# Accept either AZURE_OPENAI_KEY or the older AZURE_OPENAI_API_KEY name if provided
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
# Accept multiple deployment/env var names for compatibility
AZURE_OPENAI_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_DEPLOYMENT")
    or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    or os.getenv("AZURE_OPENAI_MODEL")
)
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2023-10-01-preview")
AUTOMATIONS_URL = os.getenv("AUTOMATIONS_SERVICE_URL", "http://automations:8000")
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")
OLLAMA_MCP_AGENT_URL = os.getenv("OLLAMA_MCP_AGENT_URL", "http://ollama-mcp-agent:3000")
RELEASES_URL = os.getenv("RELEASES_SERVICE_URL", "http://localhost:8004")

# DTOs for automation generation
class TestStep(BaseModel):
    action: str
    expected_result: str | None = None

class AutomationGenerateRequest(BaseModel):
    test_case_id: str | None = None
    title: str
    description: str | None = None
    preconditions: str | None = None
    steps: list[TestStep] | None = None

class AutomationOut(BaseModel):
    title: str
    framework: str
    script_outline: str
    notes: str

class ExecutionAutomationOut(BaseModel):
    automation_id: str | None = None
    title: str
    framework: str
    script_outline: str
    notes: str
    actions_taken: str | None = None


class AutomationDraftOut(BaseModel):
    title: str
    framework: str
    script_outline: str
    notes: str
    actions_taken: str | None = None
    exec_success: bool = False
    exec_error: str | None = None
    transcript: str | None = None
    video_filename: str | None = None
    video_path: str | None = None
    generation_mode: str | None = None
    metadata: dict = {}


class AutomationChatRequest(BaseModel):
    test_case_id: str
    message: str
    history: list[dict] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    # When true, attempt to execute the requested actions (record a video) via the Ollama MCP agent
    execute: bool = False


class AutomationChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    reply: str
    suggested_script: str | list[str] | None = None
    exec_success: bool = False
    exec_error: str | None = None
    video_filename: str | None = None
    video_path: str | None = None

    @field_validator("suggested_script")
    @classmethod
    def _coerce_script(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            try:
                return "\n".join(str(line) for line in value)
            except Exception:
                return "\n".join(["".join(value)])
        return str(value)

class ExecutionGenerateRequest(BaseModel):
    test_case_id: str

class GitPushRequest(BaseModel):
    test_case_id: str
    provider: Literal["github", "gitlab", "azure"] = "github"
    repo_url: str | None = None
    base_branch: str | None = None
    ssh_key_name: str | None = None
    auto_execute: bool = False  # Future: trigger execution after PR

REQ_URL = os.getenv("REQUIREMENTS_SERVICE_URL", "http://localhost:8001")
TC_URL = os.getenv("TESTCASES_SERVICE_URL", "http://localhost:8002")
INTERNAL_FRONTEND_BASE_URL = os.getenv("INTERNAL_FRONTEND_BASE_URL", "http://frontend:5173")

app = FastAPI(
    title="Testcase Generator Service",
    version="1.0.0",
    description="""AI-powered test case and automation generation service using Ollama LLM.
    
    ## Features
    - Generate test cases from requirements using AI
    - Create automation scripts from test cases
    - Support for multiple generation modes (replace, append)
    - Customizable generation amount
    - Integration with Ollama for LLM inference
    - Playwright script generation
    
    ## Use Cases
    - Automatically generate test cases from requirements
    - Create Playwright automation scripts
    - Accelerate test creation process
    - Maintain consistency in test format
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "generation", "description": "AI-powered test and automation generation"},
        {"name": "health", "description": "Service health and status"}
    ]
)


async def _execute_script_with_retries(client: httpx.AsyncClient, script: str, video_filename: str | None = None, *,
    record_video: bool = True,
    max_retries: int = 2,
    base_timeout: int = 90,
    max_video_bytes: int = 50_000_000,
) -> dict:
    """Execute a Playwright script via Playwright-MCP with retries and per-request timeouts.

    Returns the parsed JSON response from the MCP execute endpoint.
    """
    url = f"{PLAYWRIGHT_MCP_URL}/execute"
    # Rewrite localhost URLs to Docker-internal URLs before execution
    exec_script = _rewrite_localhost_in_text(script)
    payload = {
        "script": exec_script,
        "record_video": bool(record_video),
    }
    if video_filename:
        payload["video_path"] = video_filename
    # Offer a hint to the MCP about max allowed video size (agent may ignore)
    payload["max_video_size_bytes"] = int(max_video_bytes)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        timeout = base_timeout + (attempt - 1) * 30  # 90s, 120s
        try:
            resp = await client.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                # Wait for the browser session from the timed-out request to finish
                await asyncio.sleep(10)
                continue
            # final attempt failed -> raise
            raise last_exc


async def call_chat(client: httpx.AsyncClient, prompt: str, *, model: str | None = None, stream: bool = False, fmt: str | None = None, functions: list | None = None, timeout: int = 90) -> dict:
    """Call either Azure OpenAI Chat or local Ollama /api/generate and return a dict with a text response.

    Returns a dict similar to Ollama's /api/generate response: keys like 'response' or 'output'.
    """
    # Azure path
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT:
        try:
            url = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
            payload: dict = {"messages": [{"role": "user", "content": prompt}], "temperature": 0}
            # Request JSON output format when fmt="json" is specified
            if fmt == "json":
                payload["response_format"] = {"type": "json_object"}
            # Use the modern tools API (functions is deprecated in newer models like GPT-5.x)
            if functions:
                payload["tools"] = [{"type": "function", "function": f} for f in functions]
                payload["tool_choice"] = "auto"
            resp = await client.post(url, json=payload, headers={"api-key": AZURE_OPENAI_KEY}, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            out = {"response": content, "output": content, "raw": data}

            # Extract tool_calls from the modern tools API response
            tool_calls_raw = message.get("tool_calls") or []
            if tool_calls_raw:
                mapped = []
                for tc in tool_calls_raw:
                    func = tc.get("function") or {}
                    args = func.get("arguments")
                    try:
                        if isinstance(args, str):
                            args = json.loads(args)
                    except Exception:
                        pass
                    mapped.append({"function": {"name": func.get("name"), "arguments": args}})
                out["message"] = {"tool_calls": mapped}

            # Also handle legacy function_call response (older API versions)
            fc = message.get("function_call")
            if fc and "message" not in out:
                args = fc.get("arguments")
                try:
                    if isinstance(args, str):
                        args = json.loads(args)
                except Exception:
                    pass
                out["message"] = {"tool_calls": [{"function": {"name": fc.get("name"), "arguments": args}}]}
            return out
        except Exception as azure_err:
            # Azure failed (DNS/unreachable etc.) — fall back to Ollama path below
            print(f"call_chat: Azure OpenAI failed ({type(azure_err).__name__}: {azure_err}), falling back to Ollama")

    # Fallback: Ollama HTTP API
    resp = await client.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model or OLLAMA_MODEL, "prompt": prompt, "stream": stream, "format": fmt},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# Setup standardized error handlers
setup_all_error_handlers(app)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/execute-script-debug")
async def execute_script_debug(payload: dict):
    """Temporary debug endpoint to execute a script (useful when hot-reloading during development)."""
    script = (payload.get("script") or "").strip()
    test_case_id = payload.get("test_case_id")
    if not script:
        raise HTTPException(status_code=400, detail="Missing script")

    video_filename = f"{(test_case_id or 'manual')}_{int(datetime.now(timezone.utc).timestamp())}.webm"
    exec_success = False
    exec_error = None
    actions_taken = None
    video_saved = False

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            exec_data = await _execute_script_with_retries(client, script, video_filename, record_video=True)
            exec_success = bool(exec_data.get("success"))
            actions_taken = exec_data.get("actions_taken") or exec_data.get("message") or ""
            exec_error = exec_data.get("error")
            video_saved = bool(exec_data.get("video_saved"))
        except Exception as e:
            exec_error = str(e)

    resp = {
        "exec_success": exec_success,
        "exec_error": exec_error,
        "actions_taken": actions_taken,
        "video_filename": video_filename if video_saved else None,
        "video_path": f"/videos/{video_filename}" if video_saved else None,
        "video_saved": video_saved,
    }

    return resp

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _js_single_quoted(value: str) -> str:
    """Return a safe single-quoted JS string literal."""
    v = (value or "").strip()
    if (len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"'))):
        v = v[1:-1]
    v = v.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{v}'"


def format_steps_for_mcp(steps) -> str:
    """Convert test case steps (list/dict/str) into a useful prompt string."""
    if not steps:
        return ""
    if isinstance(steps, str):
        return steps
    if isinstance(steps, list):
        lines: list[str] = []
        for i, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                action = (step.get("action") or "").strip()
                expected = (step.get("expected_result") or "").strip()
                if expected:
                    lines.append(f"{i}. {action} (Expected: {expected})")
                else:
                    lines.append(f"{i}. {action}")
            else:
                lines.append(f"{i}. {str(step)}")
        return "\n".join(lines)
    if isinstance(steps, dict):
        # Best effort: common shape {steps:[...]}
        inner = steps.get("steps")
        return format_steps_for_mcp(inner) if inner is not None else str(steps)
    return str(steps)


def _split_args(arg_text: str) -> list[str]:
    """Split a comma-separated argument string while respecting quotes."""
    s = (arg_text or "").strip()
    if not s:
        return []
    args: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for ch in s:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            current.append(ch)
            quote = ch
            continue
        if ch == ",":
            part = "".join(current).strip()
            if part:
                args.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        args.append(tail)
    return args


_ACTION_LINE_RE = re.compile(r"^Action:\s*(?P<name>[a-zA-Z_][a-zA-Z0-9_-]*)\((?P<args>.*)\)\s*(?:-|$)")


def build_script_from_actions_log(actions_taken: str) -> str:
    """Convert Playwright-MCP action log lines into runnable Playwright JS."""
    if not actions_taken:
        return "// No actions captured"
    script_lines: list[str] = []
    for raw_line in actions_taken.split("\n"):
        line = raw_line.strip()
        if not line.startswith("Action:"):
            continue
        m = _ACTION_LINE_RE.match(line)
        if not m:
            continue
        action_name = m.group("name")
        args_str = (m.group("args") or "").strip()
        args = [a.strip() for a in _split_args(args_str)]

        # Strip obvious trailing artifacts (e.g. "- ok") if any slipped into args
        cleaned_args: list[str] = []
        for a in args:
            cleaned_args.append(a.strip())
        args = cleaned_args

        if action_name in ["navigate", "goto"] and args:
            script_lines.append(f"await page.goto({_js_single_quoted(rewrite_localhost_url(args[0]))});")
        elif action_name == "click" and args:
            script_lines.append(f"await page.click({_js_single_quoted(args[0])});")
        elif action_name in ["fill", "type"] and len(args) >= 2:
            script_lines.append(f"await page.fill({_js_single_quoted(args[0])}, {_js_single_quoted(args[1])});")
        elif action_name in ["press", "press_key"] and args:
            script_lines.append(f"await page.keyboard.press({_js_single_quoted(args[0])});")
        elif action_name == "wait" and args:
            ms_text = args[0].strip().strip('"\'')
            ms = int(ms_text) if ms_text.isdigit() else 1000
            script_lines.append(f"await page.waitForTimeout({ms});")

    return "\n".join(script_lines) or "// No actions captured"


_URL_RE = re.compile(r"(https?://[^\s)\]}]+)")

# Also match bare localhost-ish hosts that users often type in steps.
_BARE_LOCALHOST_RE = re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d{2,5})?\b")


_RAN_CODE_RE = re.compile(r"### Ran Playwright code\n(?P<code>.*?)(?:\n\n###|\Z)", re.DOTALL)


def _extract_playwright_code_blocks(text: str) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for m in _RAN_CODE_RE.finditer(text):
        code = (m.group("code") or "").strip()
        if not code:
            continue
        out.append(code)
    return out


def _rewrite_goto_lines(code: str) -> str:
    """Best-effort: rewrite localhost-like URLs inside page.goto() calls to internal frontend."""
    if not code:
        return code

    def _replace(match: re.Match) -> str:
        url = match.group("url")
        rewritten = rewrite_localhost_url(url)
        return f"page.goto('{rewritten}')"

    return re.sub(r"page\.goto\(\s*['\"](?P<url>[^'\"]+)['\"]\s*\)", _replace, code)


async def _execute_tool_calls_via_playwright_agent(client: httpx.AsyncClient, tool_calls: list) -> dict:
    """Convert a list of tool_calls (from Azure function_call mapping) into a Playwright script and execute via the playwright-mcp-agent `/execute` endpoint.

    Returns the JSON response from the agent.
    """
    if not tool_calls:
        return {"success": False, "error": "no tool_calls"}

    # Build a simple script from the tool calls. This is heuristic and covers common browser_* tools.
    lines: list[str] = []
    for tc in tool_calls:
        func = tc.get("function") if isinstance(tc, dict) else tc
        if not func:
            continue
        name = func.get("name")
        args = func.get("arguments") or {}
        if name in ("browser_navigate", "navigate", "goto"):
            url = args.get("url") or args.get("target") or args.get("value")
            if url:
                lines.append(f"await page.goto({_js_single_quoted(rewrite_localhost_url(url))});")
        elif name in ("browser_click", "click"):
            sel = args.get("selector") or args.get("element") or args.get("target") or args.get("text")
            if sel:
                lines.append(f"await page.click({_js_single_quoted(sel)});")
        elif name in ("browser_fill", "fill", "type"):
            sel = args.get("selector") or args.get("element") or args.get("target")
            val = args.get("value") or args.get("text") or args.get("keys") or ""
            if sel:
                lines.append(f"await page.fill({_js_single_quoted(sel)}, {_js_single_quoted(val)});")
        elif name in ("browser_wait_for", "wait_for", "wait"):
            t = int(args.get("time") or args.get("ms") or 1)
            # assume seconds
            lines.append(f"await page.waitForTimeout({int(t) * 1000});")
        elif name in ("browser_run_code",):
            code = args.get("code") or ""
            # try to unwrap wrapper if present
            code = _unwrap_playwright_script_to_page_only(code)
            lines.append(code)
        else:
            # Unknown tool: try to represent as comment
            lines.append(f"// Unsupported tool call: {name} {json.dumps(args)}")

    if not lines:
        return {"success": False, "error": "no script generated from tool_calls"}

    script = "\n".join(lines)
    payload = {"script": script, "record_video": False}
    try:
        resp = await client.post(f"{PLAYWRIGHT_MCP_URL.rstrip('/')}/execute", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def build_script_from_agent_transcript(transcript) -> str:
    """Extract runnable Playwright code from the Ollama-MCP agent transcript."""
    if not transcript or not isinstance(transcript, list):
        return "// No actions captured"

    blocks: list[str] = []
    for entry in transcript:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") != "tool":
            continue
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        blocks.extend(_extract_playwright_code_blocks(content))

    if not blocks:
        return "// No actions captured"

    # Each block may contain multiple lines (e.g., navigation); rewrite URLs where helpful.
    rewritten = [_rewrite_goto_lines(b) for b in blocks]
    return "\n".join(rewritten)


def rewrite_localhost_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw

    try:
        # Normalize common human-entered forms like "localhost:5173" (no scheme).
        if "://" not in raw and re.match(r"^(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d{2,5})?(?:/|$)", raw):
            raw = f"http://{raw}"

        parsed = urlparse(raw)

        if parsed.scheme and parsed.netloc and parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
            internal = urlparse(INTERNAL_FRONTEND_BASE_URL)
            if internal.scheme and internal.netloc:
                return parsed._replace(scheme=internal.scheme, netloc=internal.netloc).geturl()
    except Exception:
        return raw
    return raw


_LOCALHOST_URL_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d{2,5})?")

def _rewrite_localhost_in_text(text: str) -> str:
    if not text:
        return text
    # Match full URLs (including scheme) to avoid double http:// after rewriting
    return _LOCALHOST_URL_RE.sub(lambda m: rewrite_localhost_url(m.group(0)), text)


async def _fetch_json_optional(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        resp = await client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


async def _build_llm_execution_context(client: httpx.AsyncClient, test_case: dict) -> tuple[str, dict]:
    """Build a context block for the LLM and a structured metadata payload.

    Includes:
    - Test case title/description/preconditions
    - Linked requirements (full objects) when ids are available
    - Linked releases (full objects) when ids are available
    """
    metadata = test_case.get("metadata") or {}

    requirement_ids: list[str] = []
    primary_req = (test_case.get("requirement_id") or "").strip()
    if primary_req:
        requirement_ids.append(primary_req)

    for key in ("requirement_ids", "linked_requirement_ids", "linked_requirements"):
        val = metadata.get(key)
        if isinstance(val, list):
            for rid in val:
                rid_s = str(rid).strip()
                if rid_s:
                    requirement_ids.append(rid_s)

    # de-dupe while preserving order
    seen = set()
    requirement_ids = [x for x in requirement_ids if not (x in seen or seen.add(x))]

    requirements_full: list[dict] = []
    for rid in requirement_ids:
        req_obj = await _fetch_json_optional(client, f"{REQ_URL}/requirements/{rid}")
        if req_obj:
            requirements_full.append(req_obj)

    release_ids: list[str] = []
    for key in ("release_ids", "linked_release_ids", "releases"):
        val = metadata.get(key)
        if isinstance(val, list):
            for relid in val:
                relid_s = str(relid).strip()
                if relid_s:
                    release_ids.append(relid_s)

    # Also pull release_ids from linked requirements
    for req_obj in requirements_full:
        relid = (req_obj.get("release_id") or "").strip() if isinstance(req_obj, dict) else ""
        if relid:
            release_ids.append(relid)

    seen_rel = set()
    release_ids = [x for x in release_ids if not (x in seen_rel or seen_rel.add(x))]

    releases_full: list[dict] = []
    for relid in release_ids:
        rel_obj = await _fetch_json_optional(client, f"{RELEASES_URL}/releases/{relid}")
        if rel_obj:
            releases_full.append(rel_obj)

    ctx_lines: list[str] = []
    if requirements_full:
        ctx_lines.append("Linked Requirements (full):")
        ctx_lines.append(str(requirements_full))
    else:
        ctx_lines.append("Linked Requirements (full): none")

    if releases_full:
        ctx_lines.append("Linked Releases (full):")
        ctx_lines.append(str(releases_full))
    else:
        ctx_lines.append("Linked Releases (full): none")

    ctx_text = "\n".join(ctx_lines)
    ctx_meta = {
        "context_requirements": requirements_full,
        "context_releases": releases_full,
        "context_requirement_ids": requirement_ids,
        "context_release_ids": release_ids,
    }

    return ctx_text, ctx_meta


def build_fallback_script_from_steps(steps) -> str:
    """Best-effort script when MCP/LLM execution cannot produce actions."""
    if not steps:
        return "// TODO: No steps provided"

    lines: list[str] = []
    if isinstance(steps, str):
        steps_iter = [steps]
    elif isinstance(steps, list):
        steps_iter = steps
    else:
        steps_iter = [steps]

    for i, step in enumerate(steps_iter, start=1):
        if isinstance(step, dict):
            action = (step.get("action") or "").strip()
            expected = (step.get("expected_result") or "").strip()
        else:
            action = str(step).strip()
            expected = ""

        if not action:
            continue

        lines.append(f"// Step {i}: {action}")
        if expected:
            lines.append(f"// Expected: {expected}")

        url_match = _URL_RE.search(action)
        if url_match:
            lines.append(f"await page.goto({_js_single_quoted(rewrite_localhost_url(url_match.group(1)))});")
            continue

        # Handle bare localhost-like hosts without a scheme.
        bare_match = _BARE_LOCALHOST_RE.search(action)
        if bare_match:
            lines.append(f"await page.goto({_js_single_quoted(rewrite_localhost_url(bare_match.group(0)))});")
            continue

        # Wait hints like "wait 1500" or "wait for 2 seconds"
        lowered = action.lower()
        if "wait" in lowered:
            num_match = re.search(r"(\d+)", lowered)
            if num_match:
                ms = int(num_match.group(1))
                # If it looks like seconds, convert (heuristic)
                if "second" in lowered and ms < 1000:
                    ms *= 1000
                lines.append(f"await page.waitForTimeout({ms});")
            else:
                lines.append("await page.waitForTimeout(1000);")
            continue

    # Ensure a tiny tail wait so recordings are non-trivial
    lines.append("await page.waitForTimeout(1000);")
    return "\n".join(lines)

def simple_gherkin(requirement_title: str, requirement_desc: str | None, idx: int) -> str:
    desc = (requirement_desc or "").strip()
    extra = f"\n    And context: {desc}" if desc else ""
    return (
        f"Feature: {requirement_title}\n\n"
        f"  Scenario: Auto-generated scenario #{idx}\n"
        f"    Given the system is ready\n"
        f"    When the user triggers '{requirement_title}'\n"
        f"    Then the expected outcome is achieved{extra}\n"
    )


class StructuredStep(BaseModel):
    action: str = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)


StructuredPriority = Literal["critical", "high", "medium", "low"]


class StructuredTestcase(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=1)
    priority: StructuredPriority = "medium"
    steps: list[StructuredStep] = Field(..., min_length=1)


class GenerateStructuredRequest(BaseModel):
    requirement_id: str


class GenerateStructuredResponse(BaseModel):
    testcase: StructuredTestcase
    generator: str
    model: str
    attempts: int


class SuiteTestcase(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=1)
    priority: StructuredPriority = "medium"
    steps: list[StructuredStep] = Field(..., min_length=1)
    test_type: Literal["manual"] = "manual"


class GenerateTestSuiteRequest(BaseModel):
    requirement_id: str
    positive_amount: int = Field(3, ge=3, le=10)
    negative_amount: int = Field(2, ge=2, le=10)


class GenerateTestSuiteResponse(BaseModel):
    positive_tests: list[SuiteTestcase] = Field(..., min_length=3)
    negative_tests: list[SuiteTestcase] = Field(..., min_length=2)
    generator: str
    model: str
    attempts: int


def _strip_markdown_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_first_json_object(text: str) -> str | None:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _fallback_structured_testcase(requirement_title: str, requirement_desc: str | None) -> StructuredTestcase:
    title = f"{requirement_title} - Quick Test"
    description = (requirement_desc or "Generate a basic validation test.").strip() or "Generate a basic validation test."
    steps = [
        StructuredStep(action="Open the application", expected_result="The application loads successfully"),
        StructuredStep(action=f"Perform the main action related to: {requirement_title}", expected_result="The action completes without errors"),
        StructuredStep(action="Verify the outcome", expected_result="The expected result is visible and correct"),
    ]
    return StructuredTestcase(title=title, description=description, priority="medium", steps=steps)


async def generate_structured_testcase_with_ollama(
    client: httpx.AsyncClient,
    requirement_title: str,
    requirement_desc: str | None,
) -> tuple[StructuredTestcase | None, int]:
    schema_hint = (
        '{"title":"...","description":"...","priority":"critical|high|medium|low","steps":[{"action":"...","expected_result":"..."}]}'
    )

    base_prompt = (
        "You are a QA engineer. Generate exactly ONE manual test case for the requirement. "
        "Output JSON ONLY (no markdown, no code fences, no explanation). "
        "The JSON MUST match this schema exactly: "
        f"{schema_hint}. "
        "Constraints: title is short and specific; description is 1-3 sentences; priority is one of critical|high|medium|low; "
        "steps is an array of 3-10 objects; each step must have non-empty action and expected_result.\n\n"
        f"Requirement title: {requirement_title}\n"
        f"Requirement description: {requirement_desc or 'N/A'}\n"
    )

    last_error: str | None = None
    for attempt in range(1, 4):
        prompt = base_prompt
        if last_error:
            prompt += (
                "\nYour previous output did not validate. "
                f"Validation error: {last_error}. "
                "Return corrected JSON ONLY matching the schema exactly."
            )

        try:
            data = await call_chat(client, prompt, model=OLLAMA_MODEL, stream=False, fmt="json", timeout=90)
            text = (data.get("response") or data.get("output") or "").strip()
            text = _strip_markdown_code_fences(text)
            json_text = _extract_first_json_object(text) or text
            parsed = json.loads(json_text)
            tc = StructuredTestcase.model_validate(parsed)
            return tc, attempt
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
        except Exception as e:
            last_error = str(e)

    return None, 3


def _fallback_test_suite(requirement_title: str, requirement_desc: str | None) -> tuple[list[SuiteTestcase], list[SuiteTestcase]]:
    desc = (requirement_desc or "").strip()
    base_desc = desc or "Validate expected behavior and error handling."

    pos = [
        SuiteTestcase(
            title=f"{requirement_title} - Happy path",
            description=base_desc,
            priority="high",
            steps=[
                StructuredStep(action="Open the application", expected_result="The application loads"),
                StructuredStep(action=f"Perform the main flow for: {requirement_title}", expected_result="The operation succeeds"),
                StructuredStep(action="Verify the outcome", expected_result="The expected result is shown"),
            ],
        ),
        SuiteTestcase(
            title=f"{requirement_title} - Input validation",
            description="Verify inputs are accepted when valid.",
            priority="medium",
            steps=[
                StructuredStep(action="Navigate to the relevant screen", expected_result="The screen is visible"),
                StructuredStep(action="Enter valid inputs", expected_result="Inputs are accepted"),
                StructuredStep(action="Submit/save", expected_result="The request is processed successfully"),
            ],
        ),
        SuiteTestcase(
            title=f"{requirement_title} - Persistence",
            description="Verify the change is persisted and can be reloaded.",
            priority="medium",
            steps=[
                StructuredStep(action="Perform the main action", expected_result="The action completes"),
                StructuredStep(action="Refresh/reload", expected_result="The state reflects the completed action"),
                StructuredStep(action="Re-open the relevant view", expected_result="The persisted data is visible"),
            ],
        ),
    ]

    neg = [
        SuiteTestcase(
            title=f"{requirement_title} - Invalid input",
            description="Verify invalid input is rejected with a clear error.",
            priority="high",
            steps=[
                StructuredStep(action="Navigate to the relevant screen", expected_result="The screen is visible"),
                StructuredStep(action="Enter invalid input", expected_result="The UI indicates invalid input"),
                StructuredStep(action="Submit/save", expected_result="An error is shown and the request is not processed"),
            ],
        ),
        SuiteTestcase(
            title=f"{requirement_title} - Missing required data",
            description="Verify required fields are enforced.",
            priority="medium",
            steps=[
                StructuredStep(action="Leave required fields empty", expected_result="Validation messages are shown"),
                StructuredStep(action="Attempt to submit", expected_result="Submission is blocked"),
                StructuredStep(action="Fill required fields", expected_result="Validation clears"),
            ],
        ),
    ]

    return pos, neg


async def generate_test_suite_with_ollama(
    client: httpx.AsyncClient,
    requirement_title: str,
    requirement_desc: str | None,
    positive_amount: int,
    negative_amount: int,
) -> tuple[GenerateTestSuiteResponse | None, int]:
    schema_hint = (
        '{"positive_tests":[{"title":"...","description":"...","priority":"critical|high|medium|low","steps":[{"action":"...","expected_result":"..."}],"test_type":"manual"}],'
        '"negative_tests":[{"title":"...","description":"...","priority":"critical|high|medium|low","steps":[{"action":"...","expected_result":"..."}],"test_type":"manual"}]}'
    )

    base_prompt = (
        "You are a QA engineer. Generate a test suite for the requirement. "
        "Output JSON ONLY (no markdown, no code fences, no explanation). "
        "The JSON MUST match this schema exactly: "
        f"{schema_hint}. "
        f"You MUST generate at least {positive_amount} positive_tests and at least {negative_amount} negative_tests. "
        "Each test must include title, description, priority, and 3-10 steps (action + expected_result). "
        "Do not include any additional keys.\n\n"
        f"Requirement title: {requirement_title}\n"
        f"Requirement description: {requirement_desc or 'N/A'}\n"
    )

    last_error: str | None = None
    for attempt in range(1, 4):
        prompt = base_prompt
        if last_error:
            prompt += (
                "\nYour previous output did not validate. "
                f"Validation error: {last_error}. "
                "Return corrected JSON ONLY matching the schema exactly."
            )

        try:
            data = await call_chat(client, prompt, model=OLLAMA_MODEL, stream=False, fmt="json", timeout=120)
            text = (data.get("response") or data.get("output") or "").strip()
            text = _strip_markdown_code_fences(text)
            json_text = _extract_first_json_object(text) or text
            parsed = json.loads(json_text)

            # Validate shape first
            positive_tests = parsed.get("positive_tests") if isinstance(parsed, dict) else None
            negative_tests = parsed.get("negative_tests") if isinstance(parsed, dict) else None
            if not isinstance(positive_tests, list) or not isinstance(negative_tests, list):
                raise ValidationError.from_exception_data(
                    "GenerateTestSuiteResponse",
                    [
                        {"loc": ("positive_tests",), "msg": "missing or not a list", "type": "value_error"},
                        {"loc": ("negative_tests",), "msg": "missing or not a list", "type": "value_error"},
                    ],
                )

            # Coerce to our response model (enforces min lengths etc.)
            resp_model = GenerateTestSuiteResponse.model_validate(
                {
                    "positive_tests": positive_tests,
                    "negative_tests": negative_tests,
                    "generator": "ollama",
                    "model": OLLAMA_MODEL,
                    "attempts": attempt,
                }
            )

            # Enforce requested minimums (in case caller changed amounts)
            if len(resp_model.positive_tests) < positive_amount or len(resp_model.negative_tests) < negative_amount:
                raise ValidationError.from_exception_data(
                    "GenerateTestSuiteResponse",
                    [
                        {"loc": ("positive_tests",), "msg": "not enough positive tests", "type": "value_error"},
                        {"loc": ("negative_tests",), "msg": "not enough negative tests", "type": "value_error"},
                    ],
                )

            return resp_model, attempt
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
        except Exception as e:
            last_error = str(e)

    return None, 3


async def generate_with_ollama(client: httpx.AsyncClient, requirement_title: str, requirement_desc: str | None, idx: int) -> str | None:
    prompt = (
        "You are a QA engineer. Generate a concise Gherkin scenario for this requirement. "
        "Include Given/When/Then steps only."
        f"\nRequirement: {requirement_title}\nDescription: {requirement_desc or 'N/A'}\n"
        f"Scenario index: {idx}\n"
    )
    try:
        data = await call_chat(client, prompt, model=OLLAMA_MODEL, stream=False, timeout=60)
        text = (data.get("response") or data.get("output") or "").strip()
        return text or None
    except Exception:
        return None


async def generate_automation_with_ollama(client: httpx.AsyncClient, test_case_title: str, description: str, preconditions: str, steps: list) -> str | None:
    steps_text = "\n".join([f"{i + 1}. Action: {s.action}\n   Expected: {s.expected_result or 'N/A'}" for i, s in enumerate(steps)]) if steps else "No steps defined"
    prompt = (
        "You are an automation engineer. Generate a complete Playwright script for this test case.\n"
        "The script should be executable JavaScript code that can be passed to Playwright's page object.\n"
        "Use async/await syntax and include all necessary browser navigation, interactions, and assertions.\n"
        "Do NOT include any imports or browser launch code - just the test logic itself.\n"
        "The code will be executed as: await (async function(page, context, browser) { YOUR_CODE_HERE })(page, context, browser)\n\n"
        f"Test Case Title: {test_case_title}\n"
        f"Description: {description or 'N/A'}\n"
        f"Preconditions: {preconditions or 'N/A'}\n\n"
        f"Test Steps:\n{steps_text}\n\n"
        "Generate ONLY the JavaScript code without any markdown formatting, explanations, or comments.\n"
        "Example format:\n"
        "await page.goto('https://example.com');\n"
        "await page.click('button#login');\n"
        "await page.fill('input[name=\"username\"]', 'testuser');\n"
        "const title = await page.title();\n"
        "if (title !== 'Expected Title') throw new Error('Title mismatch');\n"
    )

    try:
        data = await call_chat(client, prompt, model=OLLAMA_MODEL, stream=False, timeout=120)
        text = (data.get("response") or data.get("output") or "").strip()
        text = _strip_markdown_code_fences(text)
        text = _unwrap_playwright_script_to_page_only(text)

        # Remove surrounding code fences if present
        if text.startswith("```"):
            lines = text.split('\n')
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = '\n'.join(lines).strip()

        return text or None
    except Exception:
        return None


def _format_step_for_llm(step, idx: int) -> tuple[str, str]:
    if isinstance(step, dict):
        action = str(step.get("action") or "").strip()
        expected = str(step.get("expected_result") or "").strip()
        if not action:
            action = f"Step {idx}"
        return action, expected
    text = str(step).strip()
    return text or f"Step {idx}", ""


def _unwrap_playwright_script_to_page_only(script: str) -> str:
    """Best-effort normalization for Playwright MCP runner.

    The Playwright MCP agent wraps provided code into: `async (page) => { ... }`.
    Therefore scripts should be plain `await page.*` statements, not their own IIFEs.
    """

    text = (script or "").strip()
    if not text:
        return ""

    text = _strip_markdown_code_fences(text).strip()

    # Unwrap a few common wrappers the LLM sometimes adds.
    for _ in range(0, 3):
        m = re.search(
            r"async\s*function\s*\(\s*page\s*,\s*context\s*,\s*browser\s*\)\s*\{([\s\S]*?)\}\s*\)\s*\(\s*page\s*,\s*context\s*,\s*browser\s*\)",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        m = re.search(
            r"async\s*\(\s*page\s*\)\s*=>\s*\{([\s\S]*?)\}\s*\)\s*\(\s*page\s*\)",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        break

    # If the model still mentions context/browser, prevent ReferenceError.
    # This keeps execution from crashing when those identifiers are unused.
    if re.search(r"\bcontext\b|\bbrowser\b", text):
        text = "const context = undefined;\nconst browser = undefined;\n" + text

    return text.strip()


def _build_script_from_tool_calls(tool_calls_executed: list) -> str:
    """Build a clean, readable Playwright script from the structured tool_calls_executed list.

    Each entry has: { iteration, name, arguments: { ... } }
    """
    if not tool_calls_executed:
        return ""

    lines: list[str] = []
    for tc in tool_calls_executed:
        name = tc.get("name", "")
        args = tc.get("arguments") or {}

        if name == "browser_navigate":
            url = args.get("url", "")
            # Show localhost for display, rewriting happens at execution time
            lines.append(f"await page.goto('{url}');")
            lines.append("await page.waitForLoadState('networkidle');")

        elif name == "browser_click":
            element = args.get("element", "")
            ref = args.get("ref", "")
            if element:
                # Use text-based selector for readability
                lines.append(f"await page.getByText('{_escape_js_string(element)}').click();")
            elif ref:
                lines.append(f"// click ref={ref}")

        elif name in ("browser_type", "browser_fill"):
            element = args.get("element", "")
            text = args.get("text", args.get("value", ""))
            submit = args.get("submit", False)
            if element:
                lines.append(f"await page.getByText('{_escape_js_string(element)}').fill('{_escape_js_string(text)}');")
            else:
                lines.append(f"await page.locator('input,textarea').first().fill('{_escape_js_string(text)}');")
            if submit:
                lines.append("await page.keyboard.press('Enter');")

        elif name == "browser_select_option":
            element = args.get("element", "")
            values = args.get("values", [])
            val_str = json.dumps(values) if isinstance(values, list) else f"['{values}']"
            lines.append(f"await page.getByText('{_escape_js_string(element)}').selectOption({val_str});")

        elif name == "browser_hover":
            element = args.get("element", "")
            lines.append(f"await page.getByText('{_escape_js_string(element)}').hover();")

        elif name == "browser_press_key":
            key = args.get("key", "")
            lines.append(f"await page.keyboard.press('{_escape_js_string(key)}');")

        elif name == "browser_wait_for":
            t = int(args.get("time", 1))
            lines.append(f"await page.waitForTimeout({t * 1000});")

        elif name == "browser_run_code":
            code = args.get("code", "")
            code = _unwrap_playwright_script_to_page_only(code)
            if code.strip():
                lines.append(code.strip())

        elif name == "browser_snapshot":
            # Snapshot is an inspection tool, not an action — skip in output script
            continue

        elif name == "browser_close":
            # Close is handled by the runtime, skip
            continue

        else:
            lines.append(f"// {name}({json.dumps(args)})")

    return "\n".join(lines)


def _escape_js_string(s: str) -> str:
    """Escape a string for use inside JS single quotes."""
    return (s or "").replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


async def generate_playwright_script_step_by_step_with_ollama(
    client: httpx.AsyncClient,
    test_case_title: str,
    description: str,
    preconditions: str,
    steps,
    base_url_hint: str,
    context_text: str = "",
    record_video: bool = False,
    video_filename: str | None = None,
) -> tuple[str | None, str, dict]:
    """Generate a Playwright script by having the MCP agent interactively execute the steps.

    The agent can inspect the actual DOM via browser_snapshot, so it uses real
    selectors instead of guessing. We then build a clean Playwright script from
    the tool calls it executed.

    Returns: (final_script_or_none, generation_log, exec_info_dict)
    """

    if not steps:
        return None, "No steps provided", {}

    if isinstance(steps, str):
        steps_list = [steps]
    elif isinstance(steps, list):
        steps_list = steps
    else:
        steps_list = [steps]

    steps_text = format_steps_for_mcp(steps_list)
    if not steps_text.strip():
        return None, "No actionable steps found", {}

    context_text = (context_text or "").strip()
    if len(context_text) > 4000:
        context_text = context_text[:4000].rstrip() + "\n[Context truncated]"

    # Build prompt for the MCP agent — it will browse the app and execute steps
    prompt_parts = [
        f"Test Case: {test_case_title}",
        f"Description: {description or 'N/A'}",
        f"Preconditions: {preconditions or 'N/A'}",
    ]
    if context_text:
        prompt_parts.append(f"\nContext:\n{context_text}")
    # The MCP agent runs inside Docker, so use the internal frontend URL
    internal_url = INTERNAL_FRONTEND_BASE_URL
    prompt_parts.append(
        f"\nThe application is running at {internal_url}."
        "\nNavigate there first, then execute each step."
        "\nUse browser_snapshot() before each interaction to see the actual page elements."
    )

    user_prompt = "\n".join(prompt_parts)

    log_lines: list[str] = []
    exec_info: dict = {}
    try:
        run_payload = {
            "prompt": user_prompt,
            "test_description": description or test_case_title,
            "steps": steps_text,
            "record_video": bool(record_video),
            "max_iterations": 15,
        }
        if record_video and video_filename:
            run_payload["video_path"] = video_filename
        run_resp = await client.post(
            f"{OLLAMA_MCP_AGENT_URL}/run",
            json=run_payload,
            timeout=300,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()

        tool_calls_executed = run_data.get("tool_calls_executed") or []
        completed = run_data.get("completed_steps")
        total = run_data.get("total_steps")
        success = run_data.get("success", False)
        video_saved = run_data.get("video_saved", False)
        actions_taken = run_data.get("actions_taken", "")

        exec_info = {
            "success": success,
            "video_saved": video_saved,
            "video_path": run_data.get("video_path"),
            "actions_taken": actions_taken,
            "completed_steps": completed,
            "total_steps": total,
        }

        # Build a clean Playwright script from the actual tool calls
        script = _build_script_from_tool_calls(tool_calls_executed)

        if completed and total:
            log_lines.append(f"MCP agent completed {completed}/{total} steps")
        log_lines.append(f"Tool calls: {len(tool_calls_executed)}, success={success}")

        if not script.strip():
            log_lines.append("No actionable tool calls captured")
            return None, "\n".join(log_lines), exec_info

        # Rewrite Docker-internal URLs back to localhost for display
        script = script.replace("http://frontend:5173", "http://localhost:5173")

        return script.strip(), "\n".join(log_lines), exec_info

    except Exception as e:
        log_lines.append(f"MCP agent error: {e}")
        # Fallback: generate script via LLM without DOM inspection
        log_lines.append("Falling back to LLM-only generation...")
        try:
            script = await _generate_script_via_llm_only(
                client, test_case_title, description, preconditions,
                steps_list, base_url_hint, context_text,
            )
            if script:
                log_lines.append("LLM fallback: OK")
                return script, "\n".join(log_lines), exec_info
        except Exception as fallback_err:
            log_lines.append(f"LLM fallback error: {fallback_err}")

        return None, "\n".join(log_lines), exec_info


async def _generate_script_via_llm_only(
    client: httpx.AsyncClient,
    test_case_title: str,
    description: str,
    preconditions: str,
    steps_list: list,
    base_url_hint: str,
    context_text: str,
) -> str | None:
    """Fallback: generate a Playwright script via a single LLM call (no DOM inspection)."""
    steps_block_lines = []
    for idx, step in enumerate(steps_list, start=1):
        action, expected = _format_step_for_llm(step, idx)
        if not action:
            continue
        line = f"  {idx}. {action}"
        if expected:
            line += f" (Expected: {expected})"
        steps_block_lines.append(line)

    if not steps_block_lines:
        return None

    steps_block = "\n".join(steps_block_lines)
    context_block = f"Context:\n{context_text}\n\n" if context_text else ""

    prompt = "".join([
        "You are an expert Playwright automation engineer.\n",
        "Generate a Playwright script implementing ALL steps below.\n",
        "Output ONLY JavaScript code (no markdown, no fences, no explanations).\n",
        "Code runs inside `async (page) => { ... }`. Only `page` exists.\n\n",
        "Use simple selectors: page.getByText('...'), page.getByRole('button', {name:'...'}), page.locator('textarea').first().\n",
        "NEVER guess complex selectors. Keep it simple.\n",
        "Add await page.waitForLoadState('networkidle') after navigation.\n",
        "Add await page.waitForTimeout(1000) after interactions that open dialogs.\n\n",
        f"App URL: {base_url_hint}\n\n",
        f"Test Case: {test_case_title}\n",
        f"Description: {description or 'N/A'}\n",
        f"Preconditions: {preconditions or 'N/A'}\n\n",
        context_block,
        f"Steps:\n{steps_block}\n\n",
        "Return the complete script as plain JavaScript.",
    ])

    data = await call_chat(client, prompt, model=OLLAMA_MODEL, stream=False, timeout=120)
    text = (data.get("response") or data.get("output") or "").strip()
    text = _strip_markdown_code_fences(text)
    if not text:
        return None
    text = _unwrap_playwright_script_to_page_only(text)
    return text.strip() or None
    return final_script, "\n".join(log_lines)

@app.get("/health")
async def health():
    # Check dependencies
    dependencies = {
        "ollama": await check_ollama(OLLAMA_URL),
        "playwright_mcp": await check_playwright_mcp(PLAYWRIGHT_MCP_URL),
        "requirements_service": await check_http_service("Requirements", REQ_URL),
        "testcases_service": await check_http_service("Testcases", TC_URL)
    }
    
    overall_status = aggregate_health_status(dependencies)
    
    return {
        "status": overall_status,
        "service": "generator",
        "timestamp": now_iso(),
        "dependencies": dependencies
    }

@app.post("/generate", response_model=GenerateResult)
async def generate(payload: GenerateRequest):
    async with httpx.AsyncClient(timeout=20) as client:
        # 1) fetch requirement
        r = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Requirement not found")
        r.raise_for_status()
        req = r.json()

        generated: list[TestcaseOut] = []

        # 2) optionally replace existing testcases
        if payload.mode == "replace":
            existing = await client.get(f"{TC_URL}/testcases", params={"requirement_id": payload.requirement_id, "limit": 200})
            existing.raise_for_status()
            for tc in existing.json():
                await client.delete(f"{TC_URL}/testcases/{tc['id']}")

        # 3) generate & store
        for i in range(1, payload.amount + 1):
            generated_gherkin = await generate_with_ollama(client, req["title"], req.get("description"), i)
            tc_payload = {
                "requirement_id": payload.requirement_id,
                "title": f"{req['title']} (auto #{i})",
                "gherkin": generated_gherkin or simple_gherkin(req["title"], req.get("description"), i),
                "status": "draft",
                "version": 1,
                "metadata": {
                    "generator": "ollama" if generated_gherkin else "stub-v1",
                    "generated_at": now_iso(),
                    "model": OLLAMA_MODEL,
                },
            }
            created = await client.post(f"{TC_URL}/testcases", json=tc_payload)
            created.raise_for_status()
            generated.append(created.json())

        return {"generated": generated}


@app.post("/generate-structured-testcase", response_model=GenerateStructuredResponse)
async def generate_structured_testcase(payload: GenerateStructuredRequest):
    """Generate a single structured testcase for a requirement.

    Note: This endpoint does NOT persist the testcase; it only returns a validated JSON structure.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Requirement not found")
        r.raise_for_status()
        req = r.json()

        tc, attempts = await generate_structured_testcase_with_ollama(
            client,
            requirement_title=req.get("title") or "Requirement",
            requirement_desc=req.get("description"),
        )
        if tc is None:
            tc = _fallback_structured_testcase(req.get("title") or "Requirement", req.get("description"))

        return {
            "testcase": tc,
            "generator": "ollama",
            "model": OLLAMA_MODEL,
            "attempts": attempts,
        }


@app.post("/generate-test-suite", response_model=GenerateTestSuiteResponse)
async def generate_test_suite(payload: GenerateTestSuiteRequest):
    """Generate a structured test suite (positive + negative tests) for review.

    Note: This endpoint does NOT persist testcases.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Requirement not found")
        r.raise_for_status()
        req = r.json()

        suite, attempts = await generate_test_suite_with_ollama(
            client,
            requirement_title=req.get("title") or "Requirement",
            requirement_desc=req.get("description"),
            positive_amount=payload.positive_amount,
            negative_amount=payload.negative_amount,
        )

        if suite is None:
            pos, neg = _fallback_test_suite(req.get("title") or "Requirement", req.get("description"))
            # Ensure we satisfy requested minimums
            if len(pos) < payload.positive_amount or len(neg) < payload.negative_amount:
                # Expand by duplicating the last element with slight title tweaks (rare fallback edge)
                while len(pos) < payload.positive_amount:
                    base = pos[-1]
                    pos.append(
                        SuiteTestcase(
                            title=f"{base.title} (alt {len(pos)+1})",
                            description=base.description,
                            priority=base.priority,
                            steps=base.steps,
                            test_type=base.test_type,
                        )
                    )
                while len(neg) < payload.negative_amount:
                    base = neg[-1]
                    neg.append(
                        SuiteTestcase(
                            title=f"{base.title} (alt {len(neg)+1})",
                            description=base.description,
                            priority=base.priority,
                            steps=base.steps,
                            test_type=base.test_type,
                        )
                    )

            return {
                "positive_tests": pos[: payload.positive_amount],
                "negative_tests": neg[: payload.negative_amount],
                "generator": "ollama",
                "model": OLLAMA_MODEL,
                "attempts": attempts,
            }

        return suite.model_dump()

@app.post("/generate-automation-from-execution", response_model=ExecutionAutomationOut)
async def generate_automation_from_execution(payload: ExecutionGenerateRequest):
    """Default: generate a script step-by-step (LLM), execute it, then persist the automation."""
    async with httpx.AsyncClient(timeout=300) as client:
        tc_resp = await client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
        if tc_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Test case not found")
        if tc_resp.status_code != 200:
            try:
                detail = tc_resp.json()
            except Exception:
                detail = tc_resp.text
            raise HTTPException(status_code=tc_resp.status_code, detail=detail)
        test_case = tc_resp.json()

        title = test_case.get("title", "Automation from Execution")
        metadata = test_case.get("metadata", {})
        description = metadata.get("description", "")
        preconditions = metadata.get("preconditions", "")
        steps = metadata.get("steps", [])

        context_text, context_meta = await _build_llm_execution_context(client, test_case)

        video_filename = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"

        # MCP agent generates the script AND executes it (with video recording)
        script_outline, generation_log, exec_info = await generate_playwright_script_step_by_step_with_ollama(
            client,
            test_case_title=title,
            description=description,
            preconditions=preconditions,
            steps=steps,
            base_url_hint="http://localhost:5173",
            context_text=context_text,
            record_video=True,
            video_filename=video_filename,
        )
        if not script_outline:
            script_outline = build_fallback_script_from_steps(steps)

        exec_success = exec_info.get("success", False)
        actions_taken = exec_info.get("actions_taken", "")
        exec_error = exec_info.get("error")
        video_saved = exec_info.get("video_saved", False)

        effective_model = f"azure:{AZURE_OPENAI_DEPLOYMENT}" if (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT) else OLLAMA_MODEL

        if exec_success:
            automation_status = "not_started"
            generation_note = f"Generated step-by-step via {effective_model} and executed on {now_iso()}."
            notes_with_code = f"{generation_note}\n\nCode:\n{script_outline}" if script_outline else generation_note
            generation_metadata = {
                "generated_at": now_iso(),
                "model": effective_model,
                "preconditions": preconditions,
                "video_filename": video_filename,
                "generation_mode": "step_by_step",
                "step_by_step_log": generation_log,
                "context": context_meta,
            }
        else:
            automation_status = "blocked"
            generation_note = (
                f"Step-by-step generation/execution failed; stored fallback script from steps on {now_iso()}. "
                f"Error: {exec_error or 'unknown'}"
            )
            generation_metadata = {
                "generated_at": now_iso(),
                "model": OLLAMA_MODEL,
                "preconditions": preconditions,
                "video_filename": video_filename,
                "generation_mode": "fallback",
                "generation_error": exec_error or "Execution failed",
                "step_by_step_log": generation_log,
                "context": context_meta,
            }
        framework = "playwright"

        automation_data = {
            "test_case_id": payload.test_case_id,
            "title": title,
            "framework": framework,
            "script": script_outline,
            "status": automation_status,
            "notes": notes_with_code if exec_success else generation_note,
            "last_actions": actions_taken,
            "metadata": generation_metadata,
        }

        # If we know a video was saved, store the absolute path used by the automations service.
        if exec_success and video_saved:
            automation_data["video_path"] = f"/videos/{video_filename}"

        save_resp = await client.post(f"{AUTOMATIONS_URL}/automations", json=automation_data)
        save_resp.raise_for_status()
        saved = save_resp.json()

        return ExecutionAutomationOut(
            automation_id=saved.get("id"),
            title=title,
            framework=framework,
            script_outline=script_outline,
            notes=generation_note,
            actions_taken=actions_taken,
        )


@app.post("/generate-automation-draft-from-execution", response_model=AutomationDraftOut)
async def generate_automation_draft_from_execution(payload: ExecutionGenerateRequest):
    """Default: generate a script step-by-step (LLM), then execute it, and return a reviewable automation draft (not persisted)."""
    async with httpx.AsyncClient(timeout=300) as client:
        tc_resp = await client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
        if tc_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Test case not found")
        if tc_resp.status_code != 200:
            try:
                detail = tc_resp.json()
            except Exception:
                detail = tc_resp.text
            raise HTTPException(status_code=tc_resp.status_code, detail=detail)
        test_case = tc_resp.json()

        title = test_case.get("title", "Automation from Execution")
        metadata = test_case.get("metadata", {})
        description = metadata.get("description", "")
        preconditions = metadata.get("preconditions", "")
        steps = metadata.get("steps", [])

        context_text, context_meta = await _build_llm_execution_context(client, test_case)

        video_filename = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
        exec_mode = "mcp_driven"

        # MCP agent generates the script AND executes it (with video recording)
        script_outline, generation_log, exec_info = await generate_playwright_script_step_by_step_with_ollama(
            client,
            test_case_title=title,
            description=description,
            preconditions=preconditions,
            steps=steps,
            base_url_hint="http://localhost:5173",
            context_text=context_text,
            record_video=True,
            video_filename=video_filename,
        )
        if not script_outline:
            script_outline = build_fallback_script_from_steps(steps)

        exec_success = exec_info.get("success", False)
        actions_taken = exec_info.get("actions_taken", "")
        transcript_out = actions_taken
        exec_error = exec_info.get("error")
        video_saved = exec_info.get("video_saved", False)

        effective_model = f"azure:{AZURE_OPENAI_DEPLOYMENT}" if (AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT) else OLLAMA_MODEL
        notes = f"Generated via MCP agent ({effective_model}) on {now_iso()}."

        generation_metadata = {
            "generated_at": now_iso(),
            "model": effective_model,
            "preconditions": preconditions,
            "video_filename": video_filename,
            "generation_mode": exec_mode,
            "step_by_step_log": generation_log,
            "context": context_meta,
        }

        framework = "playwright"

        video_path: str | None = None
        if exec_success and video_saved:
            video_path = f"/videos/{video_filename}"

        return AutomationDraftOut(
            title=title,
            framework=framework,
            script_outline=script_outline,
            notes=notes,
            actions_taken=actions_taken,
            exec_success=exec_success,
            exec_error=exec_error,
            transcript=transcript_out,
            video_filename=video_filename,
            video_path=video_path,
            generation_mode=exec_mode,
            metadata=generation_metadata,
        )


_MCP_RUN_INTENT_RE = re.compile(
    r"\b("
    r"do\s+(the\s+)?(full\s+)?steps"
    r"|do\s+all\s+steps"
    r"|perform\s+(the\s+)?steps"
    r"|execute\s+(the\s+)?(full\s+)?steps"
    r"|run\s+(the\s+)?(full\s+)?steps"
    r"|do\s+it"
    r"|please\s+(run|execute|do)"
    r"|generate\s+(the\s+)?script"
    r"|create\s+(the\s+)?script"
    r"|run\s+the\s+automation"
    r"|execute\s+the\s+automation"
    r"|automate\s+(this|it|all|the\s+steps)"
    r"|run\b"
    r"|execute\b"
    r")\b",
    re.IGNORECASE,
)


@app.post("/automation-chat", response_model=AutomationChatResponse)
async def automation_chat(payload: AutomationChatRequest):
    """Chat endpoint to help review/adjust a generated automation draft before saving."""
    # Keep this simple and safe: we only return guidance and/or a suggested script.
    history = payload.history if isinstance(payload.history, list) else []
    context = payload.context if isinstance(payload.context, dict) else {}
    current_script = (context.get("script_outline") or context.get("script") or "").strip()
    actions_taken = (context.get("actions_taken") or "").strip()
    raw_transcript = context.get("transcript")
    if isinstance(raw_transcript, str):
        transcript = raw_transcript.strip()
    elif raw_transcript is None:
        transcript = ""
    else:
        try:
            transcript = json.dumps(raw_transcript, ensure_ascii=False, indent=2)
        except Exception:
            transcript = str(raw_transcript)
    exec_error = (context.get("exec_error") or "").strip()
    video_filename = (context.get("video_filename") or "").strip()

    # Fetch the test case steps from the testcases service so the LLM has full context
    test_case_steps_text = ""
    test_case_title = ""
    test_case_description = ""
    tc_steps_raw: list = []
    async with httpx.AsyncClient(timeout=10) as tc_client:
        try:
            tc_resp = await tc_client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
            if tc_resp.status_code == 200:
                tc_data = tc_resp.json()
                test_case_title = tc_data.get("title", "")
                tc_meta = tc_data.get("metadata", {})
                test_case_description = tc_meta.get("description", "")
                tc_steps_raw = tc_meta.get("steps", [])
                test_case_steps_text = format_steps_for_mcp(tc_steps_raw)
        except Exception:
            pass  # Non-critical; we'll still answer with what context we have

    # ── Early check: does the user want us to *execute* the steps via MCP? ──
    user_wants_mcp_run = (
        bool(payload.execute)
        or (isinstance(payload.message, str) and _MCP_RUN_INTENT_RE.search(payload.message))
    )

    if user_wants_mcp_run and test_case_steps_text.strip():
        # Route directly to the MCP agent so it can inspect the real DOM
        try:
            video_filename_local = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
            async with httpx.AsyncClient(timeout=300) as run_client:
                internal_url = INTERNAL_FRONTEND_BASE_URL
                run_prompt = (
                    f"Test Case: {test_case_title}\n"
                    f"Description: {test_case_description or 'N/A'}\n"
                    f"The application is running at {internal_url}.\n"
                    "Navigate there first, then execute each step.\n"
                    "Use browser_snapshot() before each interaction to see the actual page elements."
                )
                run_payload = {
                    "prompt": run_prompt,
                    "test_description": test_case_description or test_case_title,
                    "steps": test_case_steps_text,
                    "record_video": True,
                    "video_path": video_filename_local,
                    "max_iterations": 15,
                }
                run_resp = await run_client.post(
                    f"{OLLAMA_MCP_AGENT_URL}/run",
                    json=run_payload,
                    timeout=300,
                )
                run_resp.raise_for_status()
                run_data = run_resp.json()

            tool_calls_executed = run_data.get("tool_calls_executed") or []
            success = run_data.get("success", False)
            video_saved = run_data.get("video_saved", False)
            completed = run_data.get("completed_steps")
            total = run_data.get("total_steps")

            # Build a clean Playwright script from the tool calls
            script = _build_script_from_tool_calls(tool_calls_executed)
            # Rewrite Docker-internal URLs back to localhost for display
            if script:
                script = script.replace("http://frontend:5173", "http://localhost:5173")

            reply_parts = []
            if completed and total:
                reply_parts.append(f"Executed {completed}/{total} steps via MCP agent with DOM inspection.")
            else:
                reply_parts.append(f"Ran MCP agent ({len(tool_calls_executed)} tool calls).")
            if not success:
                err = run_data.get("error", "")
                if err:
                    reply_parts.append(f"Error: {err}")

            out = AutomationChatResponse(
                reply=" ".join(reply_parts),
                suggested_script=script.strip() if script and script.strip() else None,
                exec_success=bool(success),
                exec_error=run_data.get("error") if not success else None,
            )
            if video_saved:
                out.video_filename = video_filename_local
                out.video_path = f"/videos/{video_filename_local}"
            return out

        except Exception as e:
            print(f"automation_chat: MCP /run failed: {e}")
            # Fall through to normal LLM chat
            pass

    history_lines: list[str] = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "")
        history_lines.append(f"- {role}: {content}")

    schema_hint = '{"reply":"...","suggested_script":null}'
    prompt = (
        "You are an automation engineer helping a user review and adjust a Playwright automation draft. "
        "Return a SINGLE JSON object (no extra text). Use double quotes for all JSON keys/strings. "
        f"Schema: {schema_hint}. "
        "Rules: reply is required. suggested_script is null or a full updated Playwright script body (no imports, page-only statements using the 'page' variable). "
        "If you include suggested_script, it MUST implement ALL the test case steps below, not just the first one. "
        "If you include suggested_script, encode newlines as \\n inside the JSON string.\n"
        "IMPORTANT: You do NOT have direct access to the application DOM or Playwright MCP tools in this chat. "
        "If the user asks you to run steps, generate a script based on the test case steps. Use simple selectors like page.getByText(), page.getByRole(), page.locator(). "
        "Do NOT ask the user for HTML or selectors — just generate the best script you can.\n\n"
        f"Test case title: {test_case_title or 'N/A'}\n"
        f"Test case description: {test_case_description or 'N/A'}\n"
        f"Test case steps (MUST all be automated):\n{test_case_steps_text or 'N/A'}\n\n"
        f"Test case id: {payload.test_case_id}\n"
        f"Execution error (if any): {exec_error or 'N/A'}\n"
        f"Video filename (if any): {video_filename or 'N/A'}\n"
        f"Actions taken (may be empty):\n{actions_taken or 'N/A'}\n\n"
        f"Transcript (may be empty):\n{transcript or 'N/A'}\n\n"
        f"Current script (may be empty):\n{current_script or 'N/A'}\n\n"
        "Conversation so far (role/content):\n"
        + ("\n".join(history_lines) or "N/A")
        + "\n\n"
        f"User message: {payload.message}\n"
    )

    async with httpx.AsyncClient(timeout=60) as client:
        last_error: str | None = None
        last_text: str | None = None
        for _attempt in range(1, 4):
            try:
                data = await call_chat(client, prompt if not last_error else (prompt + f"\nFix your JSON. Error: {last_error}"), model=OLLAMA_MODEL, stream=False, fmt="json", timeout=60)
                # Support both plain text responses and function_call/tool_call-style responses
                # (Azure may return a function_call with arguments instead of a content string).
                text = ""
                # If the model returned a message object (mapped to tool_calls), prefer its arguments
                message_obj = data.get("message") if isinstance(data, dict) else None
                if isinstance(message_obj, dict):
                    try:
                        tool_calls = message_obj.get("tool_calls") or []
                        if tool_calls:
                            # Take the first tool call's function.arguments if present
                            first = tool_calls[0]
                            func = first.get("function") or {}
                            args = func.get("arguments")
                            if isinstance(args, (dict, list)):
                                # If arguments already include expected keys, build a JSON reply
                                if isinstance(args, dict) and ("suggested_script" in args or "script" in args or "reply" in args):
                                    j = {"reply": args.get("reply", ""), "suggested_script": args.get("suggested_script") or args.get("script")}
                                    text = json.dumps(j, ensure_ascii=False)
                                else:
                                    # Fallback: stringify the arguments so downstream parsing can try
                                    text = json.dumps(args, ensure_ascii=False)
                            elif isinstance(args, str) and args.strip():
                                text = args.strip()
                    except Exception:
                        text = ""

                if not text:
                    text = (data.get("response") or data.get("output") or "").strip()
                last_text = text
                if not text:
                    raise ValueError("empty LLM response")
                text = _strip_markdown_code_fences(text)
                json_text = _extract_first_json_object(text) or text
                parsed = json.loads(json_text)

                # Handle double-encoded JSON: if `reply` is itself a JSON string containing `reply`, unwrap it
                if isinstance(parsed.get("reply"), str):
                    inner = parsed["reply"].strip()
                    if inner.startswith("{") and inner.endswith("}"):
                        try:
                            inner_parsed = json.loads(inner)
                            if isinstance(inner_parsed, dict) and "reply" in inner_parsed:
                                parsed = inner_parsed
                        except (json.JSONDecodeError, ValueError):
                            pass

                out = AutomationChatResponse.model_validate(parsed)
                # If the model suggested an updated script, execute it and return video metadata
                suggested = (out.suggested_script or "").strip()
                # If model did not return `suggested_script` but the free-text reply contains a script,
                # try to sanitize and execute that code as well.
                model_text_script = None
                if not suggested and isinstance(last_text, str) and last_text.strip():
                    txt = _strip_markdown_code_fences(last_text)
                    # Heuristics: script-like content contains page.* or await/page or require('playwright') or chromium.launch
                    if re.search(r"\bawait\s+page\.|page\.goto\(|require\(|chromium\.launch|browser\.newContext|newContext\(|page\.click\(", txt):
                        # Remove top-level imports and node/browser launch lines
                        lines = []
                        for line in txt.splitlines():
                            s = line.strip()
                            if re.search(r"^(const|let|var)\s+\{?\s*chromium|require\(|^import\s+|chromium\.launch|browser\.newContext|browser\.newPage|const\s+browser|manual_check\(|module\.exports", s):
                                continue
                            # remove immediate function wrappers and final invocation lines
                            if re.search(r"\b(async\s+function|\(async\s*\(|\)\s*\(page|manual_check\(\)\s*;)", s):
                                continue
                            lines.append(line)
                        candidate = "\n".join(lines).strip()
                        candidate = _unwrap_playwright_script_to_page_only(candidate)
                        # Ensure we have some page.* statements
                        if re.search(r"\bpage\.(goto|click|fill|waitFor|waitForSelector|title)\b|await\s+page\.", candidate):
                            model_text_script = candidate
                if suggested or model_text_script:
                    to_run = suggested if suggested else model_text_script
                    video_filename_local = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
                    try:
                        # Ensure the script is normalized to page-only statements
                        to_run_norm = _unwrap_playwright_script_to_page_only(_strip_markdown_code_fences(to_run))
                        exec_data = await _execute_script_with_retries(client, to_run_norm, video_filename_local, record_video=True)
                        out.exec_success = bool(exec_data.get("success"))
                        out.exec_error = exec_data.get("error")
                        video_saved = bool(exec_data.get("video_saved"))
                        if out.exec_success and video_saved:
                            out.video_filename = video_filename_local
                            out.video_path = f"/videos/{video_filename_local}"
                    except Exception as e:
                        out.exec_success = False
                        out.exec_error = str(e)

                return out
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)
                try:
                    print("automation_chat: JSON/Validation error:", last_error, "raw_data:", repr(data)[:1000])
                except Exception:
                    print("automation_chat: JSON/Validation error:", last_error)
            except Exception as e:
                last_error = str(e)
                try:
                    print("automation_chat: general error:", last_error, "raw_data:", repr(data)[:1000])
                except Exception:
                    print("automation_chat: general error:", last_error)

        # Last-resort: return whatever the model said (if anything) as plain text.
        if last_text and last_text.strip():
            return AutomationChatResponse(reply=last_text.strip(), suggested_script=None)

        return AutomationChatResponse(
            reply=(
                "I couldn't produce a valid structured response. "
                "Try asking for a specific change to the script (e.g., selectors, waits, assertions) and include what failed."
            ),
            suggested_script=None,
        )


@app.post("/execute-script")
async def execute_script(payload: dict):
    """Execute an arbitrary Playwright script via Playwright MCP and return execution + video metadata.

    Payload: { "test_case_id": str | None, "script": str }
    """
    script = (payload.get("script") or "").strip()
    test_case_id = payload.get("test_case_id")
    if not script:
        raise HTTPException(status_code=400, detail="Missing script")

    video_filename = f"{(test_case_id or 'manual')}_{int(datetime.now(timezone.utc).timestamp())}.webm"
    exec_success = False
    exec_error = None
    actions_taken = None
    video_saved = False

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            exec_data = await _execute_script_with_retries(client, script, video_filename, record_video=True)
            exec_success = bool(exec_data.get("success"))
            actions_taken = exec_data.get("actions_taken") or exec_data.get("message") or ""
            exec_error = exec_data.get("error")
            video_saved = bool(exec_data.get("video_saved"))
        except Exception as e:
            exec_error = str(e)

    resp = {
        "exec_success": exec_success,
        "exec_error": exec_error,
        "actions_taken": actions_taken,
        "video_filename": video_filename if video_saved else None,
        "video_path": f"/videos/{video_filename}" if video_saved else None,
        "video_saved": video_saved,
    }

    return resp

@app.post("/generate-automation", response_model=AutomationOut)
async def generate_automation(payload: AutomationGenerateRequest):
    """Generate automation script outline and framework recommendation from test case details."""
    async with httpx.AsyncClient(timeout=20) as client:
        automation_script = await generate_automation_with_ollama(
            client,
            payload.title,
            payload.description or "",
            payload.preconditions or "",
            payload.steps or []
        )

        if not automation_script:
            # Fallback - generate a simple Playwright script based on the steps
            if payload.steps:
                script_lines = []
                for i, step in enumerate(payload.steps):
                    action = step.action.lower()
                    if "navigate" in action or "goto" in action or "open" in action:
                        # Extract URL if present
                        words = step.action.split()
                        url = next((w for w in words if "http" in w or "." in w), "'https://example.com'")
                        if not url.startswith("'"):
                            url = f"'{url}'"
                        script_lines.append(f"await page.goto({url});")
                    elif "click" in action:
                        script_lines.append(f"// Step {i+1}: {step.action}")
                        script_lines.append(f"await page.click('button'); // TODO: Update selector")
                    elif "enter" in action or "type" in action or "fill" in action:
                        script_lines.append(f"// Step {i+1}: {step.action}")
                        script_lines.append(f"await page.fill('input', 'test value'); // TODO: Update selector and value")
                    elif "wait" in action:
                        script_lines.append(f"// Step {i+1}: {step.action}")
                        script_lines.append(f"await page.waitForTimeout(1000);")
                    else:
                        script_lines.append(f"// Step {i+1}: {step.action}")
                        script_lines.append(f"// TODO: Implement this action")
                    
                    if step.expected_result:
                        script_lines.append(f"// Expected: {step.expected_result}")
                
                automation_script = "\n".join(script_lines)
            else:
                automation_script = (
                    "await page.goto('https://example.com');\n"
                    "// TODO: Implement test steps\n"
                    "await page.waitForTimeout(1000);\n"
                )

        # Framework is always playwright since we're using Playwright-MCP
        framework = "playwright"

        # Save to automations service if test_case_id is provided
        if payload.test_case_id:
            try:
                automation_data = {
                    "test_case_id": payload.test_case_id,
                    "title": payload.title,
                    "framework": framework,
                    "script": automation_script,
                    "status": "not_started",
                    "notes": f"Generated by {OLLAMA_MODEL} on {now_iso()}",
                    "metadata": {
                        "generated_at": now_iso(),
                        "model": OLLAMA_MODEL,
                        "preconditions": payload.preconditions,
                    }
                }
                resp = await client.post(f"{AUTOMATIONS_URL}/automations", json=automation_data)
                resp.raise_for_status()
            except Exception as e:
                print(f"Failed to save automation: {e}")

        return AutomationOut(
            title=payload.title,
            framework=framework,
            script_outline=automation_script,
            notes=f"Generated by {OLLAMA_MODEL} on {now_iso()}"
        )


@app.post("/push-test-to-git", tags=["generation"])
async def push_test_to_git_endpoint(payload: GitPushRequest):
    """
    Generate automation for a test case and push it to a Git repository as a Pull/Merge Request.
    
    This endpoint orchestrates the full workflow:
    1. Fetch test case details
    2. Generate Playwright automation script (if not already generated)
    3. Create git branch
    4. Write test file to repository
    5. Commit and push changes
    6. Create Pull/Merge Request
    7. (Optional) Return execution instructions
    
    **Environment Variables Required:**
    - TESTS_REPO_URL: Git repository URL for tests
    - TESTS_REPO_BRANCH: Base branch (default: main)
    - TEST_FILES_PATH: Path within repo for tests (default: tests/generated)
    
    **For private repos:**
    - Use ssh_key_name parameter with pre-configured SSH key
    
    **Example Response:**
    ```json
    {
      "success": true,
      "automation_id": "64f...",
      "git_result": {
        "pr_url": "https://github.com/org/repo/pull/123",
        "pr_number": 123,
        "branch_name": "feat/test-abc123-1702340000",
        "file_path": "tests/generated/user-login-abc123.spec.js"
      },
      "execution": {
        "instructions": {...}
      }
    }
    ```
    """
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Fetch test case
        tc_resp = await client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
        if tc_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Test case not found")
        tc_resp.raise_for_status()
        test_case = tc_resp.json()
        
        test_title = test_case.get("title", "Untitled Test")
        metadata = test_case.get("metadata", {})
        
        # 2. Check if automation already exists
        automations_resp = await client.get(
            f"{AUTOMATIONS_URL}/automations",
            params={"test_case_id": payload.test_case_id}
        )
        automations_resp.raise_for_status()
        automations = automations_resp.json()
        
        if automations and len(automations) > 0:
            # Use existing automation
            automation = automations[0]
            script_content = automation.get("script", "")
            automation_id = automation.get("id")
        else:
            # Generate new automation
            description = metadata.get("description", "")
            preconditions = metadata.get("preconditions", "")
            steps_data = metadata.get("steps", [])
            
            # Convert steps to TestStep format
            steps = []
            if isinstance(steps_data, list):
                for step in steps_data:
                    if isinstance(step, dict):
                        steps.append(TestStep(
                            action=step.get("action", ""),
                            expected_result=step.get("expected_result")
                        ))

            # Generate script content locally (do not call our own HTTP route with a relative URL)
            script_content = await generate_automation_with_ollama(
                client,
                test_title,
                description,
                preconditions,
                steps,
            )
            if not script_content:
                # Fall back to the same step-based script used by /generate-automation
                script_content = format_steps_for_mcp(steps_data) or "// TODO: Implement test steps"

            # Save to automations service
            save_resp = await client.post(
                f"{AUTOMATIONS_URL}/automations",
                json={
                    "test_case_id": payload.test_case_id,
                    "title": test_title,
                    "framework": "playwright",
                    "script": script_content,
                    "status": "not_started",
                    "notes": f"Generated by {OLLAMA_MODEL} on {now_iso()}",
                    "metadata": {
                        "generated_at": now_iso(),
                        "model": OLLAMA_MODEL,
                        "preconditions": preconditions,
                    },
                },
            )
            save_resp.raise_for_status()
            
            # Fetch the saved automation ID
            automations_resp = await client.get(
                f"{AUTOMATIONS_URL}/automations",
                params={"test_case_id": payload.test_case_id}
            )
            automations_resp.raise_for_status()
            new_automations = automations_resp.json()
            automation_id = new_automations[0].get("id") if new_automations else None
        
        # 3. Push to Git
        try:
            git_result = await push_test_to_git(
                test_case_id=payload.test_case_id,
                test_title=test_title,
                script_content=script_content,
                provider=payload.provider,
                repo_url=payload.repo_url,
                base_branch=payload.base_branch,
                ssh_key_name=payload.ssh_key_name
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Git push failed: {str(e)}")
        
        # 4. Get execution instructions
        execution_info = await trigger_test_execution(
            branch_name=git_result["branch_name"],
            file_path=git_result["file_path"],
            repo_name=git_result["repo_name"]
        )
        
        return {
            "success": True,
            "automation_id": automation_id,
            "test_case_id": payload.test_case_id,
            "test_title": test_title,
            "git_result": git_result,
            "execution": execution_info,
            "message": f"Test pushed to Git successfully! PR/MR created at {git_result.get('pr_url')}"
        }


        return AutomationOut(
            title=payload.title,
            framework=framework,
            script_outline=automation_script,
            notes=f"Generated by {OLLAMA_MODEL} on {now_iso()}"
        )

