"""
LangGraph-based automation generation pipeline (v2).

The primary mode is an interactive ReAct agent that drives the browser
via Playwright MCP tool calls — the LLM can snapshot, click, type,
and navigate in real-time rather than generating a blind script.

A legacy generate → execute → repair pipeline is kept as fallback.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Annotated, Optional

import httpx
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END

from llm import llm_generate, llm_generate_with_usage, get_llm, LLM_MODEL

logger = logging.getLogger(__name__)

# ── Route prefix: Docker-internal route interceptors + Keycloak auto-login ───
ROUTE_PREFIX = (
    "// Route interceptors: remap localhost URLs to Docker-internal hostnames\n"
    "await page.route('**localhost:8080/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8080', 'keycloak:8080');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:5173/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:5173', 'frontend:5173');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "// API service interceptors\n"
    "await page.route('**localhost:8001/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8001', 'requirements:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8002/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8002', 'testcases:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8004/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8004', 'releases:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8005/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8005', 'executions:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8006/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8006', 'automations:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8007/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8007', 'git:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8008/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8008', 'toabrkia:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8009/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8009', 'testcase-migration:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "await page.route('**localhost:8013/**', async route => {\n"
    "  const url = route.request().url().replace('localhost:8013', 'generator-v2:8000');\n"
    "  await route.continue({ url });\n"
    "});\n"
    "\n"
    "// Auto-login via Keycloak if needed\n"
    "async function ensureKeycloakLogin(pg, user = 'admin', pass = 'admin123') {\n"
    "  await pg.goto('http://frontend:5173/');\n"
    "  await pg.waitForTimeout(1500);\n"
    "  const isKeycloak = await pg.locator('#username').count() > 0;\n"
    "  if (isKeycloak) {\n"
    "    await pg.locator('#username').fill(user);\n"
    "    await pg.locator('#password').fill(pass);\n"
    "    await pg.locator('#kc-login').click();\n"
    "    await pg.waitForURL('**/TestPlan**', { timeout: 10000 }).catch(() => {});\n"
    "    await pg.waitForTimeout(1000);\n"
    "  }\n"
    "}\n"
    "await ensureKeycloakLogin(page);\n"
    "\n"
)

_LOCALHOST_RE = re.compile(r'https?://localhost:5173')


# ═════════════════════════════════════════════════════════════════════════════
# State
# ═════════════════════════════════════════════════════════════════════════════

class AutomationState(BaseModel):
    """Typed state flowing through the automation generation graph."""
    # Inputs
    test_case_id: str
    test_case_title: str = ""
    description: str = ""
    preconditions: str = ""
    steps: list = Field(default_factory=list)
    gherkin: str = ""
    base_url: str = "http://frontend:5173"
    kg_block: str = ""
    memory_block: str = ""
    context_text: str = ""
    auth_headers: dict = Field(default_factory=dict)
    playwright_mcp_url: str = "http://playwright-mcp-agent:3000"

    # Working state
    script: str = ""
    generation_log: list[str] = Field(default_factory=list)
    exec_success: bool = False
    exec_error: str = ""
    actions_taken: str = ""
    video_filename: str = ""
    video_saved: bool = False
    repair_attempts: int = 0
    max_repairs: int = 2
    started_at: float = 0.0

    # Token usage tracking
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    model_config = {"arbitrary_types_allowed": True}


# ═════════════════════════════════════════════════════════════════════════════
# Helpers (shared with v1 via copy — intentionally decoupled)
# ═════════════════════════════════════════════════════════════════════════════

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_MARKDOWN_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_markdown_code_fences(text: str) -> str:
    text = _MARKDOWN_FENCE_RE.sub("", text)
    text = _MARKDOWN_FENCE_END_RE.sub("", text)
    return text.strip()


_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def _strip_think_tags(text: str) -> str:
    """Strip qwen3-style <think>...</think> blocks from LLM output."""
    return _THINK_RE.sub("", text).strip()


def _unwrap_playwright_script_to_page_only(text: str) -> str:
    """If the LLM wrapped the code in a function/IIFE, unwrap to page-only body."""
    stripped = text.strip()
    # Detect patterns like module.exports = async (page) => { ... }
    patterns = [
        r"module\.exports\s*=\s*async\s*\(\s*(?:\{\s*page\s*\}|page)\s*\)\s*=>\s*\{",
        r"(?:export\s+default\s+)?async\s+function\s*\w*\s*\(\s*(?:\{\s*page\s*\}|page)\s*\)\s*\{",
        r"async\s*\(\s*(?:\{\s*page\s*\}|page)\s*\)\s*=>\s*\{",
    ]
    import re as _re
    for pat in patterns:
        m = _re.search(pat, stripped)
        if m:
            body = stripped[m.end():]
            # Find matching closing brace
            depth = 1
            for i, ch in enumerate(body):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return body[:i].strip()
            return body.strip()
    return stripped


def _format_steps_for_prompt(steps) -> str:
    lines = []
    for i, step in enumerate(steps, 1):
        if isinstance(step, dict):
            action = step.get("action", "")
            expected = step.get("expected_result", "")
            lines.append(f"Step {i}: {action}")
            if expected:
                lines.append(f"  Expected: {expected}")
        else:
            lines.append(f"Step {i}: {step}")
    return "\n".join(lines)


_URL_RE = re.compile(r'(https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?[^\s\'"]*)')
_BENIGN_PATTERNS = re.compile(
    r"(?:WebSocket\s+connection|ERR_CONNECTION_REFUSED|failed\s+to\s+connect|"
    r"vite.*?client|React\s+DevTools|net::ERR_|favicon\.ico|HMR|hot\s+module)",
    re.IGNORECASE,
)
_EXEC_ERROR_PATTERNS = re.compile(
    r"(?:TypeError|ReferenceError|SyntaxError|EvalError|RangeError|URIError|"
    r"TimeoutError|page\.evaluate|Unhandled\s+rejection|Cannot\s+read\s+propert|"
    r"is\s+not\s+a\s+function|is\s+not\s+defined|ActionError|"
    r"FAIL(?:ED)?[:\s]|CRASH|Execution\s+error|Script\s+error)",
    re.IGNORECASE,
)


def _detect_hidden_errors(actions_taken: str | None, exec_error: str | None) -> str | None:
    for text in (actions_taken, exec_error):
        if not text:
            continue
        for m in _EXEC_ERROR_PATTERNS.finditer(text):
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 200)
            snippet = text[start:end].strip()
            if _BENIGN_PATTERNS.search(snippet):
                continue
            return snippet
    if actions_taken and "Page URL: about:blank" in actions_taken:
        return "Navigation appears to have failed – page is still at about:blank"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Page snapshot helper
# ═════════════════════════════════════════════════════════════════════════════

async def _fetch_page_snapshot(mcp_url: str, base_url: str) -> str:
    """Navigate to the app, log in via Keycloak, and return an accessibility snapshot."""
    login_script = ROUTE_PREFIX + (
        f"await page.goto('{base_url}/');\n"
        "await page.waitForTimeout(2000);\n"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{mcp_url}/snapshot",
                json={"login_script": login_script},
                timeout=30,
            )
            data = resp.json()
            if data.get("success"):
                return data.get("snapshot", "")
    except Exception as e:
        logger.warning(f"Page snapshot failed: {e}")
    return ""


# ═════════════════════════════════════════════════════════════════════════════
# Graph nodes
# ═════════════════════════════════════════════════════════════════════════════

async def _node_generate(state: AutomationState) -> dict:
    """Generate Playwright script from test case using Azure OpenAI."""
    steps_text = _format_steps_for_prompt(state.steps)

    # Fetch a live page snapshot so the LLM can see real elements
    page_snapshot = await _fetch_page_snapshot(state.playwright_mcp_url, state.base_url)

    prompt = "".join([
        "You are an expert Playwright automation engineer.\n",
        "Generate a COMPLETE Playwright script body (JavaScript, no imports, no function wrapper).\n",
        "The code runs inside `async (page) => { ... }` — only `page` is available.\n\n",
        "AUTHENTICATION IS ALREADY HANDLED — DO NOT ADD LOGIN CODE.\n",
        "The user is ALREADY LOGGED IN. Start on the dashboard.\n\n",
        "RULES:\n",
        "- Use page.getByRole(), page.getByText(), page.getByLabel(), page.locator()\n",
        "- NEVER use page.evaluate()\n",
        "- ALWAYS use { exact: false } for text matching\n",
        "- Add { timeout: 10000 } to .click(), .fill(), .waitFor()\n",
        "- Start with: await page.waitForTimeout(2000);\n",
        "- End with: await page.waitForTimeout(2000);\n\n",
        "DROPDOWN / SELECT INTERACTION (Radix UI — CRITICAL):\n",
        "The app uses Radix UI Select dropdowns. They are NOT native <select> elements.\n",
        "To interact with a dropdown:\n",
        "  1. Click the trigger button: await page.getByRole('combobox').click({ timeout: 10000 });\n",
        "     Or if there are multiple: page.getByRole('combobox', { name: 'placeholder text' })\n",
        "  2. Wait for the listbox to appear: await page.getByRole('listbox').waitFor({ timeout: 5000 });\n",
        "  3. Click the option: await page.getByRole('option', { name: 'option text', exact: false }).click({ timeout: 10000 });\n",
        "  4. Wait for it to close: await page.waitForTimeout(500);\n",
        "NEVER use page.selectOption() — it only works on native <select> elements.\n",
        "NEVER try to .fill() a dropdown — they are not text inputs.\n",
        "If the trigger has placeholder text like 'Select release', use: page.getByRole('combobox', { name: 'Select release' })\n\n",
        "DIALOG INTERACTION:\n",
        "- Dialogs open via portals. Wait after clicking a trigger button: await page.waitForTimeout(1000);\n",
        "- Use page.getByRole('dialog') to scope interactions inside a dialog.\n",
        "- For form fields in dialogs: page.getByRole('dialog').getByLabel('field label')\n\n",
        "DATE INPUT FIELDS:\n",
        "The app uses native HTML date inputs (<input type='date'>).\n",
        "To set a date value, use .fill() with YYYY-MM-DD format:\n",
        "  await page.getByLabel('Target Date').fill('2025-06-15', { timeout: 10000 });\n",
        "Or by ID: await page.locator('#target_date').fill('2025-06-15', { timeout: 10000 });\n",
        "NEVER click on the native date picker popup. Just .fill() the input directly.\n",
        "NEVER use page.type() for dates. Always use .fill() with the full date string.\n\n",
        f"Docker base URL: {state.base_url}\n\n",
    ])

    if state.kg_block:
        prompt += f"=== APP KNOWLEDGE GRAPH ===\n{state.kg_block}\n=== END ===\n\n"
    if state.memory_block:
        prompt += f"=== PAST LEARNINGS ===\n{state.memory_block}\n=== END ===\n\n"

    if page_snapshot:
        # Truncate to avoid blowing up the context window
        snap = page_snapshot[:4000]
        prompt += (
            "=== LIVE PAGE ACCESSIBILITY SNAPSHOT ===\n"
            "Below is the actual accessibility tree of the app dashboard right now.\n"
            "Use these EXACT element roles, names, and labels in your script.\n"
            f"{snap}\n"
            "=== END SNAPSHOT ===\n\n"
        )

    prompt += f"Test Case: {state.test_case_title}\n"
    prompt += f"Description: {state.description or 'N/A'}\n"
    prompt += f"Preconditions: {state.preconditions or 'N/A'}\n"
    # Only include gherkin if there are no structured steps (they contain the
    # same information and doubling the content makes qwen3 spend too many
    # thinking tokens).
    if state.gherkin and not state.steps:
        prompt += f"Gherkin:\n{state.gherkin}\n"
    if state.context_text:
        prompt += f"\nContext:\n{state.context_text[:2000]}\n"
    prompt += f"\nSteps:\n{steps_text}\n\nGenerate the COMPLETE script now."

    try:
        text, usage = await llm_generate_with_usage(prompt, timeout=90)
        text = _strip_think_tags(text)
        text = _strip_markdown_code_fences(text)
        text = _unwrap_playwright_script_to_page_only(text)
        if text and len(text) > 20:
            return {
                "script": text,
                "generation_log": state.generation_log + ["LangChain generate: OK"],
                "started_at": time.monotonic(),
                "prompt_tokens": state.prompt_tokens + usage.get("prompt_tokens", 0),
                "completion_tokens": state.completion_tokens + usage.get("completion_tokens", 0),
                "total_tokens": state.total_tokens + usage.get("total_tokens", 0),
            }
    except Exception as e:
        logger.error(f"LangChain generation failed: {e}")

    logger.warning("LangChain generate produced no usable script")
    return {
        "generation_log": state.generation_log + ["LangChain generate: FAILED"],
        "started_at": time.monotonic(),
    }


def _rewrite_localhost_urls(script: str) -> str:
    """Replace localhost:5173 URLs with Docker-internal frontend:5173."""
    return _LOCALHOST_RE.sub('http://frontend:5173', script)


async def _node_execute(state: AutomationState) -> dict:
    """Execute the script via Playwright MCP with route prefix and retries."""
    if not state.script:
        return {"exec_success": False, "exec_error": "No script to execute"}

    # Rewrite localhost URLs and prepend Docker route interceptors + Keycloak login
    script = _rewrite_localhost_urls(state.script)
    prepared_script = ROUTE_PREFIX + script

    video_filename = f"{state.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
    url = f"{state.playwright_mcp_url}/execute"
    payload = {
        "script": prepared_script,
        "video_path": video_filename,
        "record_video": True,
        "max_video_size_bytes": 50_000_000,
    }

    max_retries = 2
    exec_timeout = 120
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=exec_timeout) as client:
                resp = await client.post(url, json=payload, timeout=exec_timeout)
                resp.raise_for_status()
                data = resp.json()
                success = bool(data.get("success"))
                actions = data.get("actions_taken") or data.get("message") or ""
                error = data.get("error") or ""
                video_saved = bool(data.get("video_saved"))

                hidden = _detect_hidden_errors(actions, error)
                if hidden and success:
                    success = False
                    error = error or hidden

                return {
                    "exec_success": success,
                    "exec_error": error,
                    "actions_taken": actions,
                    "video_filename": video_filename,
                    "video_saved": video_saved,
                    "generation_log": state.generation_log + [
                        f"Execute: {'OK' if success else 'FAILED'}"
                    ],
                }
        except Exception as e:
            last_error = e
            logger.warning(f"Execute attempt {attempt} failed: {e}")
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(2)
                continue

    return {
        "exec_success": False,
        "exec_error": str(last_error),
        "generation_log": state.generation_log + [f"Execute: ERROR {last_error}"],
    }


def _should_repair(state: AutomationState) -> str:
    """Conditional edge: repair if failed and under retry budget."""
    if state.exec_success:
        return "output"
    if state.repair_attempts < state.max_repairs:
        return "repair"
    return "output"


async def _node_repair(state: AutomationState) -> dict:
    """Ask LLM to fix the failed script."""
    prompt = "".join([
        "You are an expert Playwright automation engineer. A script failed.\n",
        "Return ONLY the corrected JavaScript code (no markdown, no explanation).\n",
        "The code runs inside `async (page) => { ... }`.\n\n",
        "DO NOT ADD LOGIN CODE — auth is handled externally.\n\n",
        "RULES:\n",
        "- Use page.getByRole(), page.getByText(), page.getByLabel(), page.locator()\n",
        "- NEVER use page.evaluate()\n",
        "- ALWAYS use { exact: false } for text matching\n",
        "- Add { timeout: 10000 } to interactions\n\n",
        "DROPDOWN / SELECT FIX GUIDE (Radix UI — CRITICAL):\n",
        "The app uses Radix UI Select, NOT native <select>. Common dropdown errors:\n",
        "- selectOption() fails → Replace with: click combobox trigger, wait for listbox, click option\n",
        "- 'option not found' → The listbox was not open. Click the combobox trigger first.\n",
        "- Timeout on option → Add await page.getByRole('listbox').waitFor({ timeout: 5000 }) after clicking trigger\n",
        "Correct pattern:\n",
        "  await page.getByRole('combobox', { name: 'placeholder' }).click({ timeout: 10000 });\n",
        "  await page.getByRole('listbox').waitFor({ timeout: 5000 });\n",
        "  await page.getByRole('option', { name: 'value', exact: false }).click({ timeout: 10000 });\n",
        "  await page.waitForTimeout(500);\n",
        "NEVER use page.selectOption(). NEVER .fill() a dropdown.\n\n",
        "DATE INPUT FIX GUIDE:\n",
        "Date inputs use <input type='date'>. Common date errors:\n",
        "- Clicking/typing individual date parts fails → Use .fill('YYYY-MM-DD') on the input directly\n",
        "- Date picker popup blocks interaction → Don't click the calendar icon, just .fill() the input\n",
        "Correct pattern: await page.getByLabel('Date Label').fill('2025-06-15', { timeout: 10000 });\n\n",
    ])

    if state.kg_block:
        prompt += f"=== APP KNOWLEDGE GRAPH ===\n{state.kg_block}\n=== END ===\n\n"
    if state.memory_block:
        prompt += f"=== PAST LEARNINGS ===\n{state.memory_block}\n=== END ===\n\n"

    prompt += f"Original script:\n{state.script}\n\n"
    if state.exec_error:
        # Strip the "Ran Playwright code" section that contains the full script dump
        # with route prefix — we don't want the LLM to reproduce that
        clean_error = state.exec_error
        ran_idx = clean_error.find("### Ran Playwright code")
        if ran_idx > 0:
            clean_error = clean_error[:ran_idx].strip()
        prompt += f"Error:\n{clean_error[:2000]}\n\n"
    if state.actions_taken:
        # Also strip the code dump from transcript
        clean_transcript = state.actions_taken
        ran_idx = clean_transcript.find("### Ran Playwright code")
        if ran_idx > 0:
            clean_transcript = clean_transcript[:ran_idx].strip()
        prompt += f"Transcript:\n{clean_transcript[:2000]}\n\n"
    prompt += "Make minimal edits to fix the failure. Return the FULL corrected script."
    prompt += "\nDO NOT include route interceptors or ensureKeycloakLogin — that is handled externally."

    attempt = state.repair_attempts + 1
    try:
        text, usage = await llm_generate_with_usage(prompt, timeout=90)
        text = _strip_think_tags(text)
        text = _strip_markdown_code_fences(text)
        text = _unwrap_playwright_script_to_page_only(text)
        if text and len(text) > 20:
            return {
                "script": text,
                "repair_attempts": attempt,
                "generation_log": state.generation_log + [f"Repair {attempt}: OK"],
                "prompt_tokens": state.prompt_tokens + usage.get("prompt_tokens", 0),
                "completion_tokens": state.completion_tokens + usage.get("completion_tokens", 0),
                "total_tokens": state.total_tokens + usage.get("total_tokens", 0),
            }
    except Exception as e:
        logger.error(f"Repair attempt {attempt} failed: {e}")

    return {
        "repair_attempts": attempt,
        "generation_log": state.generation_log + [f"Repair {attempt}: FAILED"],
    }


async def _node_output(state: AutomationState) -> dict:
    """Final node — just mark completion."""
    return {
        "generation_log": state.generation_log + [
            f"Final: {'SUCCESS' if state.exec_success else 'FAILED'} "
            f"(repairs={state.repair_attempts})"
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# ReAct Agent — LLM drives Playwright MCP interactively
# ═════════════════════════════════════════════════════════════════════════════

class BrowserSession:
    """Manages a persistent Playwright MCP session for the ReAct agent."""

    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.session_id: str | None = None
        self._client: httpx.AsyncClient | None = None
        self.action_log: list[dict] = []
        self._snapshots: list[str] = []
        self._ref_map: dict[str, dict] = {}

    async def start(self):
        self._client = httpx.AsyncClient(timeout=60)
        resp = await self._client.post(f"{self.mcp_url}/session/create")
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Session create failed: {data.get('error')}")
        self.session_id = data["session_id"]

    async def call_tool(self, name: str, args: dict | None = None) -> str:
        resp = await self._client.post(
            f"{self.mcp_url}/session/{self.session_id}/tool",
            json={"name": name, "args": args or {}},
            timeout=60,
        )
        data = resp.json()
        text = data.get("result", "")
        if name == "browser_snapshot":
            self._snapshots.append(text)
            self._update_ref_map(text)
        return text

    async def close(self, video_path: str = "") -> bool:
        video_saved = False
        if self.session_id:
            try:
                resp = await self._client.post(
                    f"{self.mcp_url}/session/{self.session_id}/close",
                    json={"video_path": video_path},
                    timeout=30,
                )
                video_saved = resp.json().get("video_saved", False)
            except Exception:
                pass
        if self._client:
            await self._client.aclose()
        return video_saved

    # ── Ref map: parse accessibility snapshot into role/name by ref ──
    _REF_RE = re.compile(r"-\s+(\w+)\s+\"([^\"]*)\"\s+\[ref=(\w+)\]")

    def _update_ref_map(self, snapshot: str):
        for m in self._REF_RE.finditer(snapshot):
            role, name, ref = m.group(1), m.group(2), m.group(3)
            self._ref_map[ref] = {"role": role, "name": name}

    # ── Convert action log → replayable Playwright script ──
    def build_script(self) -> str:
        lines = ["await page.waitForTimeout(2000);"]
        for action in self.action_log:
            t = action["tool"]
            if t == "browser_navigate":
                lines.append(f"await page.goto('{action['url']}');")
            elif t == "browser_click":
                info = self._ref_map.get(action.get("ref", ""), {})
                role = info.get("role", "")
                name = info.get("name", action.get("element", ""))
                if role:
                    safe = name.replace("'", "\\'")
                    lines.append(
                        f"await page.getByRole('{role}', {{ name: '{safe}', exact: false }})"
                        f".click({{ timeout: 10000 }});"
                    )
                else:
                    safe = name.replace("'", "\\'")
                    lines.append(
                        f"await page.getByText('{safe}', {{ exact: false }})"
                        f".click({{ timeout: 10000 }});"
                    )
            elif t == "browser_type":
                info = self._ref_map.get(action.get("ref", ""), {})
                name = info.get("name", action.get("element", ""))
                text = action.get("text", "")
                safe_name = name.replace("'", "\\'")
                safe_text = text.replace("'", "\\'")
                lines.append(
                    f"await page.getByLabel('{safe_name}', {{ exact: false }})"
                    f".fill('{safe_text}', {{ timeout: 10000 }});"
                )
            elif t == "browser_wait":
                ms = int(action.get("seconds", 2)) * 1000
                lines.append(f"await page.waitForTimeout({ms});")
            # Skip snapshots in the generated script
        lines.append("await page.waitForTimeout(2000);")
        return "\n".join(lines)


def _make_browser_tools(session: BrowserSession):
    """Create LangChain tools bound to a live BrowserSession."""

    @tool
    async def browser_snapshot() -> str:
        """Take a snapshot of the current page to see all visible elements, their roles, names, and ref IDs. Call this BEFORE interacting with elements, and AFTER each action to verify the result."""
        result = await session.call_tool("browser_snapshot")
        session.action_log.append({"tool": "browser_snapshot"})
        return result

    @tool
    async def browser_click(element: str, ref: str) -> str:
        """Click an element on the page. Parameters: element = description (e.g. 'Submit button'), ref = exact ref ID from the latest snapshot (e.g. 'e5')."""
        result = await session.call_tool("browser_click", {"element": element, "ref": ref})
        session.action_log.append({"tool": "browser_click", "element": element, "ref": ref})
        return result

    @tool
    async def browser_type(element: str, ref: str, text: str) -> str:
        """Type text into an input field. Parameters: element = field description, ref = exact ref ID from snapshot, text = value to type."""
        result = await session.call_tool("browser_type", {"element": element, "ref": ref, "text": text})
        session.action_log.append({"tool": "browser_type", "element": element, "ref": ref, "text": text})
        return result

    @tool
    async def browser_navigate(url: str) -> str:
        """Navigate to a URL."""
        result = await session.call_tool("browser_navigate", {"url": url})
        session.action_log.append({"tool": "browser_navigate", "url": url})
        return result

    @tool
    async def browser_wait(seconds: int = 2) -> str:
        """Wait for the page to update after an action. Use 1-3 seconds."""
        result = await session.call_tool("browser_wait_for", {"time": seconds})
        session.action_log.append({"tool": "browser_wait", "seconds": seconds})
        return result

    return [browser_snapshot, browser_click, browser_type, browser_navigate, browser_wait]


async def _run_react_loop(llm, tools, system_prompt: str, max_steps: int = 30):
    """Run a manual ReAct agent loop with token tracking."""
    llm_with_tools = llm.bind_tools(tools)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Execute the test case steps now. Start by taking a snapshot of the current page."),
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for _step in range(max_steps):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        # Track token usage
        usage = (response.response_metadata or {}).get("token_usage") or {}
        if not usage:
            usage = (response.response_metadata or {}).get("usage") or {}
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        total_usage["total_tokens"] += usage.get("total_tokens", 0)

        # If no tool calls, the agent considers itself done
        if not response.tool_calls:
            break

        # Execute each tool call
        for tc in response.tool_calls:
            tool_fn = next((t for t in tools if t.name == tc["name"]), None)
            if tool_fn:
                try:
                    result = await tool_fn.ainvoke(tc["args"])
                except Exception as e:
                    result = f"Tool error: {e}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

    # Extract the agents final text message
    final_text = ""
    if messages and hasattr(messages[-1], "content"):
        final_text = messages[-1].content or ""

    return final_text, total_usage, len(messages)


async def _node_agent_run(state: AutomationState) -> dict:
    """Interactive ReAct agent that drives the browser via MCP tool calls."""
    session = BrowserSession(state.playwright_mcp_url)
    video_filename = f"{state.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
    gen_log = list(state.generation_log)

    try:
        await session.start()
        gen_log.append("Agent: session created")

        # Run route interceptors + Keycloak login inside the session browser
        setup_code = (
            f"async (page) => {{\n"
            f"{ROUTE_PREFIX}"
            f"}}"
        )
        await session.call_tool("browser_run_code", {"code": setup_code})
        gen_log.append("Agent: routes + login done")

        # Let the page settle after login
        await session.call_tool("browser_wait_for", {"time": 2})

        # Build the system prompt
        steps_text = _format_steps_for_prompt(state.steps)

        system_prompt = (
            "You are a browser automation agent. You control a web browser by calling tools.\n\n"
            "WORKFLOW — repeat for each test step:\n"
            "1. Call browser_snapshot to see all elements on the page (roles, names, ref IDs)\n"
            "2. Find the element you need from the snapshot output\n"
            "3. Call browser_click or browser_type with the EXACT ref from the snapshot\n"
            "4. Call browser_snapshot again to verify the action worked\n\n"
            "RULES:\n"
            "- ALWAYS snapshot before interacting — never guess refs\n"
            "- Use the exact ref string (e.g. 'e5') from the snapshot\n"
            "- For dropdowns: click the combobox trigger, snapshot to see the listbox options, then click the option\n"
            "- For date inputs: use browser_type with YYYY-MM-DD format\n"
            "- If an element is not visible, try browser_wait(2) then snapshot again\n"
            "- After the LAST step, call browser_snapshot once to capture the final state\n"
            "- When all steps are complete, respond with a summary of what you did\n\n"
            f"The user is already logged in and on the dashboard.\n\n"
        )

        if state.kg_block:
            system_prompt += f"=== APP KNOWLEDGE GRAPH ===\n{state.kg_block}\n=== END ===\n\n"

        system_prompt += (
            f"Test Case: {state.test_case_title}\n"
            f"Description: {state.description or 'N/A'}\n"
            f"Preconditions: {state.preconditions or 'N/A'}\n"
            f"Steps:\n{steps_text}\n"
        )

        # Run the ReAct loop
        tools = _make_browser_tools(session)
        llm = get_llm(timeout=60)
        summary, usage, msg_count = await _run_react_loop(
            llm, tools, system_prompt, max_steps=30,
        )
        gen_log.append(f"Agent: completed ({msg_count} messages)")

        # Build a replayable Playwright script from the recorded actions
        script = session.build_script()
        actions_text = summary or "Agent completed all steps."

        # Close session and finalize video
        video_saved = await session.close(video_path=video_filename)

        return {
            "script": script,
            "exec_success": True,
            "exec_error": "",
            "actions_taken": actions_text,
            "video_filename": video_filename,
            "video_saved": video_saved,
            "generation_log": gen_log + ["Agent: SUCCESS"],
            "started_at": time.monotonic(),
            "prompt_tokens": state.prompt_tokens + usage.get("prompt_tokens", 0),
            "completion_tokens": state.completion_tokens + usage.get("completion_tokens", 0),
            "total_tokens": state.total_tokens + usage.get("total_tokens", 0),
        }

    except Exception as e:
        logger.error(f"Agent run failed: {e}", exc_info=True)
        # Ensure session is closed
        try:
            await session.close()
        except Exception:
            pass
        return {
            "exec_success": False,
            "exec_error": str(e),
            "generation_log": gen_log + [f"Agent: FAILED — {e}"],
            "started_at": time.monotonic(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# Graph builder
# ═════════════════════════════════════════════════════════════════════════════

_compiled_graph = None


def build_automation_graph():
    """Build default graph: ReAct agent → output."""
    graph = StateGraph(AutomationState)

    graph.add_node("agent_run", _node_agent_run)
    graph.add_node("output", _node_output)

    graph.add_edge(START, "agent_run")
    graph.add_edge("agent_run", "output")
    graph.add_edge("output", END)

    return graph.compile()


def build_legacy_graph():
    """Fallback: blind generate → execute → repair loop."""
    graph = StateGraph(AutomationState)

    graph.add_node("generate", _node_generate)
    graph.add_node("execute", _node_execute)
    graph.add_node("repair", _node_repair)
    graph.add_node("output", _node_output)

    graph.add_edge(START, "generate")
    graph.add_edge("generate", "execute")
    graph.add_conditional_edges("execute", _should_repair, {
        "repair": "repair",
        "output": "output",
    })
    graph.add_edge("repair", "execute")
    graph.add_edge("output", END)

    return graph.compile()


def get_automation_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_automation_graph()
    return _compiled_graph
