import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
import re
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator
import httpx
import asyncio
from bson import ObjectId
from shared.db import get_db, close_client
from shared.models import GenerateRequest, GenerateResult, TestcaseOut
from shared.errors import setup_all_error_handlers
from shared.health import check_ollama, check_playwright_mcp, check_http_service, aggregate_health_status
from shared.settings import CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth


def _fwd_headers(request: Request) -> dict:
    """Extract Authorization header for service-to-service forwarding."""
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes
from git_integration import push_test_to_git, trigger_test_execution

logger = get_logger(__name__)

# Ollama configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
# Default model aligned with docker-compose (keep in sync)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
# Deterministic model sampling params to reduce nondeterministic outputs
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "1"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "2048"))
AUTOMATIONS_URL = os.getenv("AUTOMATIONS_SERVICE_URL", "http://automations:8000")
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")
OLLAMA_MCP_AGENT_URL = os.getenv("OLLAMA_MCP_AGENT_URL", "http://ollama-mcp-agent:3000")
RELEASES_URL = os.getenv("RELEASES_SERVICE_URL", "http://localhost:8004")

# ---------------------------------------------------------------------------
# App Knowledge Graph — static map of the frontend UI for LLM context
# ---------------------------------------------------------------------------
# This gives the LLM immediate, accurate awareness of every page/route,
# navigation elements, button labels, selector strategies, and API endpoints
# so it can generate correct Playwright code without needing a live DOM snapshot.
# Maintaining this in code is cheaper than an MCP round-trip per step.

APP_KNOWLEDGE_GRAPH: dict = {
    "app_name": "TestMaster",
    "framework": "React + Vite + shadcn/ui (Tailwind)",
    "base_url_docker": "http://frontend:5173",
    "selector_strategy": (
        "No data-testid attributes exist. "
        "Use role-based selectors: page.getByRole('button', {name:'...'}), page.getByRole('link', {name:'...'}), page.getByRole('heading', {name:'...'}). "
        "Use text selectors: page.getByText('exact text'). "
        "Use CSS when roles are ambiguous: page.locator('.class-name'), page.locator('input[placeholder=\"...\"]')."
    ),
    "layout": {
        "sidebar": {
            "description": "Left sidebar with navigation links. Always visible on desktop, toggleable on mobile.",
            "header": "TestMaster logo + 'QA Management' subtitle",
            "toggle_button": "aria-label='Toggle Sidebar'",
            "nav_items": [
                {"label": "Test Plan", "route": "/TestPlan"},
                {"label": "AI Insights", "route": "/AIInsights"},
                {"label": "Releases", "route": "/Releases"},
                {"label": "TOAB/RK/IA", "route": "/toab-rk-ia"},
                {"label": "Requirements", "route": "/Requirements"},
                {"label": "Test Cases", "route": "/TestCases"},
                {"label": "Testcase Migration", "route": "/testcase-migration"},
                {"label": "Automations", "route": "/Automations"},
                {"label": "Executions", "route": "/Executions"},
            ],
            "footer_items": [{"label": "Admin", "route": "/admin"}],
        },
    },
    "pages": {
        "/TestPlan": {
            "description": "Dashboard overview — stats, charts, requirement/testcase lists",
            "also": "/ (default route)",
            "key_buttons": ["New Requirement", "New Test Case"],
            "filters": ["Release filter (popover + checkboxes)", "View mode: list/board"],
            "interactive": ["StatsCard components", "Paginated requirement/testcase lists", "TestCasesByRequirement chart"],
        },
        "/Requirements": {
            "description": "List/manage requirements. Create, edit, delete, AI-generate test suites.",
            "key_buttons": ["New Requirement", "AI Test Suite", "Quick Test", "Delete (trash icon per card)"],
            "filters": ["Filter by Release (Select dropdown)"],
            "dialogs": ["RequirementDialog (create/edit)", "AdvancedAITestDialog (AI Test Suite)", "TestCaseDialog (Quick Test)", "Delete AlertDialog"],
            "empty_state": "Text 'Create your first requirement'",
        },
        "/TestCases": {
            "description": "List/manage test cases. Generate automations, execute tests.",
            "key_buttons": ["New Test Case", "Generate Automation (sparkles icon)", "Execute", "AI Generate", "Delete (trash icon)"],
            "filters": ["Filter by Requirement (Select)", "Filter by Release (Select)", "Tabs: All / Draft / Ready / Passed / Failed"],
            "dialogs": ["TestCaseDialog", "ManualExecutionDialog", "AutomationReviewDialog", "Delete AlertDialog"],
        },
        "/Automations": {
            "description": "List/manage automation scripts. Execute, view video/actions.",
            "key_buttons": ["New Automation", "Execute", "View Result", "Watch Video", "View Actions", "Delete (trash icon)"],
            "filters": ["Filter by Test Case (Select)", "Tabs: All / Ready / Passing / Failing"],
            "dialogs": ["AutomationDialog", "Video Dialog", "Actions Dialog", "Delete AlertDialog"],
        },
        "/Releases": {
            "description": "Manage releases.",
            "key_buttons": ["New Release", "Delete (trash icon)"],
            "dialogs": ["ReleaseDialog", "Delete AlertDialog"],
            "empty_state": "Text 'Create your first release'",
        },
        "/Executions": {
            "description": "View execution results. Filter by release, status.",
            "key_buttons": ["API Documentation", "View Steps", "Edit"],
            "filters": ["Filter by Release (Select)", "Tabs: All / Passed / Failed / Blocked", "View: all / manual / automated"],
            "stats": ["Total, Passed, Failed, Blocked, Pass Rate cards"],
            "dialogs": ["ExecutionDialog", "ExecutionDetailsDialog", "ApiInfoDialog"],
        },
        "/AIInsights": {
            "description": "AI-powered test analytics dashboard (mock data).",
            "key_buttons": ["Generate AI Insights", "Get Started", "Refresh Analysis"],
            "sections": ["Priority Actions", "Failure Patterns", "Root Causes", "Stability/Coverage"],
        },
        "/toab-rk-ia": {
            "description": "TOAB/RK/IA assessment management linked to releases.",
            "key_buttons": ["Create", "Delete (trash icon)"],
            "filters": ["Filter by Release (Select)"],
            "dialogs": ["ToabRkIaDialog", "Delete AlertDialog"],
        },
        "/testcase-migration": {
            "description": "4-step wizard: paste legacy code → testcase draft → automation draft → save.",
            "key_buttons": ["Analyze", "Generate automation draft", "Execute", "Save", "Back", "Reset"],
            "form_fields": ["Textarea (legacy code)", "Input (title)", "Textarea (description/preconditions)", "Step editor (add/remove)"],
        },
        "/admin": {
            "description": "Administration: tokens, repos, users, health, AI settings.",
            "tabs": ["API tokens", "Repo connections", "User management", "Service health", "AI inclusion", "Test approach"],
            "key_buttons": ["Save token", "Connect", "Add user", "Save", "Delete (per-row)"],
        },
    },
    "common_button_labels": [
        "New Requirement", "New Test Case", "New Automation", "New Release", "Create",
        "AI Test Suite", "Quick Test", "Generate Automation", "Execute", "View Result",
        "Watch Video", "View Actions", "View Steps", "Edit", "Delete", "Cancel",
        "Generate AI Insights", "Get Started", "Refresh Analysis",
        "API Documentation", "Save token", "Connect", "Save", "Analyze", "Back", "Reset",
    ],
    "aria_labels": [
        "Toggle Sidebar", "Move step up", "Move step down", "Remove step",
        "breadcrumb", "pagination", "Go to previous page", "Go to next page",
    ],
}


def _build_knowledge_graph_prompt_block(steps_text: str = "", kg: dict | None = None) -> str:
    """Build a compact prompt block from the knowledge graph, focused on pages
    the test steps are likely to touch.

    If *steps_text* mentions specific pages/routes, only include those pages
    to keep the prompt short. Otherwise include a summary of all pages.

    *kg* can be a DB-loaded knowledge graph dict.  When ``None``, falls back
    to the hardcoded ``APP_KNOWLEDGE_GRAPH``.
    """
    if kg is None:
        kg = APP_KNOWLEDGE_GRAPH
    lines: list[str] = [
        f"Application: {kg['app_name']} ({kg['framework']})",
        f"Docker base URL: {kg['base_url_docker']}",
        f"Selector strategy: {kg['selector_strategy']}",
        "",
        "Sidebar navigation links (use page.getByRole('link', {{name: '<label>'}}) to click):",
    ]
    for item in kg["layout"]["sidebar"]["nav_items"]:
        lines.append(f"  - '{item['label']}' → {item['route']}")
    lines.append(f"  - 'Admin' → /admin  (sidebar footer)")
    lines.append("")

    # Determine which pages are relevant based on step text
    lower_steps = (steps_text or "").lower()
    relevant_pages = {}
    for route, info in kg["pages"].items():
        # Include a page if steps mention its route, name, or key words
        route_lower = route.lower().strip("/")
        desc_lower = info.get("description", "").lower()
        # Always include: mentioned in steps or generic/short test
        keywords = [route_lower, route_lower.replace("/", "")]
        # Add page-specific keywords
        if "requirement" in route_lower:
            keywords.extend(["requirement", "requirements"])
        if "testcase" in route_lower or "test" in route_lower:
            keywords.extend(["test case", "testcase", "test cases"])
        if "automation" in route_lower:
            keywords.extend(["automation", "automations"])
        if "release" in route_lower:
            keywords.extend(["release", "releases"])
        if "execution" in route_lower:
            keywords.extend(["execution", "executions", "execute"])

        if not lower_steps or any(kw in lower_steps for kw in keywords):
            relevant_pages[route] = info

    # If nothing matched or very few steps, include all pages (compact)
    if len(relevant_pages) == 0:
        relevant_pages = kg["pages"]

    for route, info in relevant_pages.items():
        lines.append(f"Page: {route}")
        lines.append(f"  Description: {info.get('description', '')}")
        if info.get("also"):
            lines.append(f"  Also: {info['also']}")
        if info.get("key_buttons"):
            lines.append(f"  Buttons: {', '.join(info['key_buttons'])}")
        if info.get("filters"):
            lines.append(f"  Filters: {', '.join(info['filters'])}")
        if info.get("dialogs"):
            lines.append(f"  Dialogs: {', '.join(info['dialogs'])}")
        if info.get("empty_state"):
            lines.append(f"  Empty state: {info['empty_state']}")
        lines.append("")

    lines.append(f"Common button labels: {', '.join(kg['common_button_labels'][:15])}...")
    lines.append(f"Known aria-labels: {', '.join(kg['aria_labels'])}")

    return "\n".join(lines)

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
# Toggle whether invalid LLM outputs should be rejected (HTTP 502) or allowed to fallback
REJECT_INVALID_GENERATIONS = os.getenv("REJECT_INVALID_GENERATIONS", "true").lower() in ("1", "true", "yes")

# Knowledge Graph collection name (used by startup seeder + CRUD endpoints)
KG_COLLECTION = "knowledge_graphs"


async def _seed_default_knowledge_graph():
    """Seed the hardcoded APP_KNOWLEDGE_GRAPH into MongoDB if the collection is empty."""
    try:
        db = get_db()
        count = await db[KG_COLLECTION].count_documents({})
        if count > 0:
            return  # already seeded
        kg = APP_KNOWLEDGE_GRAPH
        doc = {
            "app_name": kg["app_name"],
            "framework": kg["framework"],
            "base_url": kg["base_url_docker"],
            "selector_strategy": kg["selector_strategy"],
            "nav_items": kg["layout"]["sidebar"]["nav_items"],
            "pages": kg["pages"],
            "common_button_labels": kg["common_button_labels"],
            "aria_labels": kg["aria_labels"],
            "is_default": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        await db[KG_COLLECTION].insert_one(doc)
        logger.info("Seeded default knowledge graph for %s", kg["app_name"])
    except Exception as e:
        logger.warning("Failed to seed knowledge graph: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("generator", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    validate_settings()
    await ensure_indexes(get_db(), ["knowledge_graph"])
    await _seed_default_knowledge_graph()
    logger.info("Generator service ready")
    yield
    await close_client()
    logger.info("Generator service stopped")


app = FastAPI(
    lifespan=lifespan,
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
    max_retries: int = 3,
    base_timeout: int = 15,
    max_video_bytes: int = 50_000_000,
) -> dict:
    """Execute a Playwright script via Playwright-MCP with retries and per-request timeouts.

    Returns the parsed JSON response from the MCP execute endpoint.
    """
    url = f"{PLAYWRIGHT_MCP_URL}/execute"
    payload = {
        "script": script,
        "record_video": bool(record_video),
    }
    if video_filename:
        payload["video_path"] = video_filename
    # Offer a hint to the MCP about max allowed video size (agent may ignore)
    payload["max_video_size_bytes"] = int(max_video_bytes)

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        timeout = base_timeout * attempt
        try:
            resp = await client.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(min(5, attempt))
                continue
            # final attempt failed -> raise
            raise last_exc


async def _ollama_generate_request(client: httpx.AsyncClient, prompt: str, extra: dict | None = None, timeout: int = 90) -> dict:
    """Helper that calls the Ollama generate endpoint with deterministic params from env.

    Returns the parsed JSON body from Ollama or raises the underlying httpx exception.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": float(OLLAMA_TEMPERATURE),
        "top_p": float(OLLAMA_TOP_P),
        "max_tokens": int(OLLAMA_MAX_TOKENS),
    }
    if extra:
        payload.update(extra)

    resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


async def _repair_and_rerun(
    client: httpx.AsyncClient,
    original_script: str,
    video_filename_base: str,
    *,
    test_case_id: str | None = None,
    exec_error: str | None = None,
    actions_taken: str | None = None,
    context_text: str = "",
    max_retries: int = 2,
    kg: dict | None = None,
) -> tuple[str, dict | None, int]:
    """Attempt to repair a failing Playwright script by calling the LLM with the error log.

    Returns: (final_script, exec_data_or_none, attempts_made)
    """
    last_exec: dict | None = None
    current_script = original_script or ""

    # Build knowledge-graph block once (uses the script itself to guess relevant pages)
    kg_block = _build_knowledge_graph_prompt_block(current_script, kg=kg)

    for attempt in range(1, max_retries + 1):
        prompt = (
            "You are an expert Playwright automation engineer. A script was executed and failed. "
            "Return ONLY the corrected JavaScript code (no markdown, no fences, no explanation). "
            "The returned code should be the full test body to be executed inside `async (page) => { ... }` and should use `await page.*` statements.\n\n"
            "CRITICAL RULES:\n"
            "- Use Playwright locator APIs: page.locator(), page.getByRole(), page.getByText(), page.getByLabel().\n"
            "- NEVER use page.evaluate() to inspect DOM elements or read className/attributes.\n"
            "- SVG elements do NOT have a string className – never call .className.split().\n"
            "- For reading text, use page.locator('selector').textContent() instead of page.evaluate.\n"
            "- For verifying elements, use page.locator('selector').waitFor() or .isVisible().\n\n"
        )
        if kg_block:
            prompt += (
                "=== APP KNOWLEDGE GRAPH (routes, buttons, selectors) ===\n"
                f"{kg_block}\n"
                "=== END KNOWLEDGE GRAPH ===\n\n"
            )
        prompt += f"Original script:\n{current_script}\n\n"
        if exec_error:
            prompt += f"Execution error:\n{exec_error}\n\n"
        if actions_taken:
            prompt += f"Actions/transcript:\n{actions_taken}\n\n"
        if context_text:
            prompt += f"Context:\n{context_text}\n\n"
        prompt += (
            "Please make minimal edits necessary to fix the failure (selectors, waits, ordering). "
            "Replace any page.evaluate() DOM reads with page.locator() equivalents. "
            "If you cannot determine a fix, return the original script unchanged."
        )

        try:
            data = await _ollama_generate_request(client, prompt, timeout=120)
            text = (data.get("response") or data.get("output") or "").strip()
            text = _strip_markdown_code_fences(text)
            candidate = _unwrap_playwright_script_to_page_only(text)
            if not candidate:
                # nothing to try
                continue

            # Execute repaired candidate
            repair_video = f"{video_filename_base}_repair{attempt}.webm"
            try:
                exec_data = await _execute_script_with_retries(client, candidate, repair_video, record_video=True)
                success = bool(exec_data.get("success"))
                last_exec = exec_data
                current_script = candidate
                # Also check for hidden errors in transcript
                repair_actions = exec_data.get("actions_taken") or ""
                repair_error = exec_data.get("error") or ""
                hidden = _detect_hidden_errors(repair_actions, repair_error)
                if hidden and success:
                    success = False
                    exec_error = hidden
                if success:
                    return current_script, last_exec, attempt
                # else loop to try again
                exec_error = exec_data.get("error") or exec_error
                actions_taken = exec_data.get("actions_taken") or actions_taken
            except Exception as e:
                exec_error = str(e)
                last_exec = {"error": exec_error}
                # try next repair
                continue
        except Exception:
            # If LLM call fails, stop early
            break

    return current_script, last_exec, max_retries


# ---------------------------------------------------------------------------
# Execution quality helpers
# ---------------------------------------------------------------------------

# Patterns that indicate a real error even when MCP `/execute` returns success:true
# NOTE: We deliberately avoid bare "Error" – it matches benign console messages
# like "[ERROR] WebSocket ..." or "ERR_CONNECTION_REFUSED" from Vite/Docker.
_EXEC_ERROR_PATTERNS = re.compile(
    r"(?:TypeError|ReferenceError|SyntaxError|EvalError|RangeError|URIError|"
    r"TimeoutError|page\.evaluate|Unhandled\s+rejection|Cannot\s+read\s+propert|"
    r"is\s+not\s+a\s+function|is\s+not\s+defined|ActionError|"
    r"FAIL(?:ED)?[:\s]|CRASH|Execution\s+error|Script\s+error)",
    re.IGNORECASE,
)

# Console noise that should NOT trigger the repair loop
_BENIGN_PATTERNS = re.compile(
    r"(?:WebSocket\s+connection|ERR_CONNECTION_REFUSED|failed\s+to\s+connect\s+to\s+websocket|"
    r"vite.*?client|React\s+DevTools|Download\s+the\s+React|net::ERR_|"
    r"favicon\.ico|HMR|hot\s+module|localhost:\d+/\@vite)",
    re.IGNORECASE,
)


def _detect_hidden_errors(actions_taken: str | None, exec_error: str | None) -> str | None:
    """Scan execution transcript for error patterns missed by the boolean *success* flag.

    Returns the first matching error snippet (or *None* when the output looks clean).
    Filters out known benign console messages from Vite, Docker networking, and dev tools.
    """
    for text in (actions_taken, exec_error):
        if not text:
            continue
        for m in _EXEC_ERROR_PATTERNS.finditer(text):
            # Extract context around the match
            start = max(0, m.start() - 120)
            end = min(len(text), m.end() + 200)
            snippet = text[start:end].strip()
            # Skip if the surrounding context is a known benign pattern
            if _BENIGN_PATTERNS.search(snippet):
                continue
            return snippet
    # Detect silent navigation failure: page remained on about:blank
    if actions_taken and "Page URL: about:blank" in actions_taken:
        return "Navigation appears to have failed – page is still at about:blank"
    return None


async def _get_page_snapshot(client: httpx.AsyncClient) -> str | None:
    """Ask the Playwright MCP for a DOM accessibility snapshot of the current page.

    Uses a lightweight script that returns the page title + URL + visible text
    via the `/execute` endpoint — much faster than spinning up the full agentic
    ollama-mcp-agent /run loop.  Returns the snapshot text or *None* on failure.
    """
    # Fast path: run a small script that harvests key selectors from the live page.
    # This avoids the 15-30s agentic loop from before.
    snapshot_script = """
// Gather accessible element info for selector guidance.
const title = document.title || '';
const url = location.href || '';
const buttons = [...document.querySelectorAll('button, [role="button"]')]
  .slice(0, 30)
  .map(b => b.textContent?.trim() || b.getAttribute('aria-label') || '')
  .filter(Boolean);
const links = [...document.querySelectorAll('a')]
  .slice(0, 30)
  .map(a => ({ text: a.textContent?.trim()?.substring(0, 60), href: a.getAttribute('href') || '' }))
  .filter(l => l.text);
const headings = [...document.querySelectorAll('h1,h2,h3,h4')]
  .slice(0, 15)
  .map(h => h.textContent?.trim())
  .filter(Boolean);
const inputs = [...document.querySelectorAll('input,textarea,select')]
  .slice(0, 20)
  .map(i => ({ tag: i.tagName.toLowerCase(), type: i.type||'', placeholder: i.placeholder||'', name: i.name||'', label: i.getAttribute('aria-label')||'' }));

JSON.stringify({ title, url, buttons, links, headings, inputs }, null, 2);
"""
    try:
        resp = await client.post(
            f"{PLAYWRIGHT_MCP_URL}/execute",
            json={"script": f"return await page.evaluate(() => {{{snapshot_script}}})", "record_video": False},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # The result text is in actions_taken
            text = data.get("actions_taken", "")
            if text and len(text) > 30:
                return text[:6000]
        return None
    except Exception:
        return None


# Setup standardized error handlers
setup_all_error_handlers(app)

# Production middleware: auth, rate limiting, CORS
setup_auth(app)
setup_rate_limiting(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Knowledge Graph CRUD  (MongoDB-backed)
# ---------------------------------------------------------------------------


class KnowledgeGraphPageCreate(BaseModel):
    route: str
    description: str = ""
    key_buttons: list[str] = []
    filters: list[str] = []
    dialogs: list[str] = []
    empty_state: str = ""
    also: str | None = None
    interactive: list[str] = []
    sections: list[str] = []
    form_fields: list[str] = []
    tabs: list[str] = []


class KnowledgeGraphNavItem(BaseModel):
    label: str
    route: str


class KnowledgeGraphCreate(BaseModel):
    app_name: str
    framework: str = ""
    base_url: str = "http://localhost:3000"
    selector_strategy: str = ""
    nav_items: list[KnowledgeGraphNavItem] = []
    pages: list[KnowledgeGraphPageCreate] = []
    common_button_labels: list[str] = []
    aria_labels: list[str] = []
    is_default: bool = False


class KnowledgeGraphUpdate(BaseModel):
    app_name: str | None = None
    framework: str | None = None
    base_url: str | None = None
    selector_strategy: str | None = None
    nav_items: list[KnowledgeGraphNavItem] | None = None
    pages: list[KnowledgeGraphPageCreate] | None = None
    common_button_labels: list[str] | None = None
    aria_labels: list[str] | None = None
    is_default: bool | None = None


def _kg_doc_to_out(doc: dict) -> dict:
    """Mongo doc → JSON-serialisable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.get("/knowledge-graphs", tags=["knowledge-graph"])
async def list_knowledge_graphs():
    db = get_db()
    docs = await db[KG_COLLECTION].find().sort("app_name", 1).to_list(100)
    return [_kg_doc_to_out(d) for d in docs]


@app.get("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def get_knowledge_graph(kg_id: str):
    db = get_db()
    doc = await db[KG_COLLECTION].find_one({"_id": ObjectId(kg_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    return _kg_doc_to_out(doc)


@app.post("/knowledge-graphs", tags=["knowledge-graph"], status_code=201)
async def create_knowledge_graph(body: KnowledgeGraphCreate):
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    # Convert page list to dict keyed by route for internal storage
    doc["pages"] = {p["route"]: p for p in doc["pages"]}
    doc["nav_items"] = [ni for ni in doc["nav_items"]]
    result = await db[KG_COLLECTION].insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@app.put("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def update_knowledge_graph(kg_id: str, body: KnowledgeGraphUpdate):
    db = get_db()
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    # Convert page list → dict keyed by route
    if "pages" in updates:
        updates["pages"] = {p["route"]: p for p in updates["pages"]}
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db[KG_COLLECTION].update_one({"_id": ObjectId(kg_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    doc = await db[KG_COLLECTION].find_one({"_id": ObjectId(kg_id)})
    return _kg_doc_to_out(doc)


@app.delete("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def delete_knowledge_graph(kg_id: str):
    db = get_db()
    result = await db[KG_COLLECTION].delete_one({"_id": ObjectId(kg_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    return {"deleted": True}


async def _load_knowledge_graph_for_app(app_name: str | None = None) -> dict | None:
    """Load a knowledge graph from MongoDB.

    If *app_name* is given, look for an exact match. Otherwise return the
    document marked ``is_default=True``, or the first available document.
    Falls back to the hardcoded ``APP_KNOWLEDGE_GRAPH`` if nothing is in the DB.
    """
    db = get_db()
    coll = db[KG_COLLECTION]
    doc = None
    if app_name:
        doc = await coll.find_one({"app_name": {"$regex": f"^{re.escape(app_name)}$", "$options": "i"}})
    if not doc:
        doc = await coll.find_one({"is_default": True})
    if not doc:
        doc = await coll.find_one()  # any
    if doc:
        return _kg_doc_to_dict(doc)
    return None


def _kg_doc_to_dict(doc: dict) -> dict:
    """Convert a MongoDB knowledge graph document into the dict format
    expected by ``_build_knowledge_graph_prompt_block``."""
    pages_raw = doc.get("pages", {})
    pages: dict = {}
    if isinstance(pages_raw, dict):
        pages = pages_raw
    elif isinstance(pages_raw, list):
        for p in pages_raw:
            route = p.get("route", "")
            if route:
                pages[route] = p
    nav_raw = doc.get("nav_items", [])
    nav_items = []
    for ni in nav_raw:
        if isinstance(ni, dict) and ni.get("label") and ni.get("route"):
            nav_items.append(ni)
    return {
        "app_name": doc.get("app_name", "Unknown"),
        "framework": doc.get("framework", ""),
        "base_url_docker": doc.get("base_url", "http://localhost:3000"),
        "selector_strategy": doc.get("selector_strategy", ""),
        "layout": {
            "sidebar": {
                "nav_items": nav_items,
            },
        },
        "pages": pages,
        "common_button_labels": doc.get("common_button_labels", []),
        "aria_labels": doc.get("aria_labels", []),
    }


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


def _rewrite_localhost_in_text(text: str) -> str:
    if not text:
        return text
    return _BARE_LOCALHOST_RE.sub(lambda m: rewrite_localhost_url(m.group(0)), text)


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
    - Test case full fields (title, gherkin, description, preconditions, status)
    - Linked requirements (all fields) when ids are available
    - Linked releases (all fields) when ids are available
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

    # -- Build readable context text for the LLM ----------------------------
    ctx_lines: list[str] = []

    # Full test case fields
    tc_title = test_case.get("title", "")
    tc_gherkin = test_case.get("gherkin", "")
    tc_status = test_case.get("status", "")
    tc_desc = metadata.get("description", "")
    tc_pre = metadata.get("preconditions", "")
    tc_steps = metadata.get("steps", [])
    ctx_lines.append("=== TEST CASE (full) ===")
    ctx_lines.append(f"Title: {tc_title}")
    if tc_desc:
        ctx_lines.append(f"Description: {tc_desc}")
    if tc_pre:
        ctx_lines.append(f"Preconditions: {tc_pre}")
    ctx_lines.append(f"Status: {tc_status}")
    if tc_gherkin:
        ctx_lines.append(f"Gherkin/BDD Scenario:\n{tc_gherkin}")
    if tc_steps:
        ctx_lines.append("Steps:")
        for i, st in enumerate(tc_steps, 1):
            if isinstance(st, dict):
                ctx_lines.append(f"  {i}. Action: {st.get('action', '')}")
                exp = st.get("expected_result", "")
                if exp:
                    ctx_lines.append(f"     Expected: {exp}")
            else:
                ctx_lines.append(f"  {i}. {st}")
    ctx_lines.append("")

    # Linked requirements (all fields)
    if requirements_full:
        ctx_lines.append("=== LINKED REQUIREMENTS ===")
        for req in requirements_full:
            ctx_lines.append(f"Requirement: {req.get('title', 'N/A')} (id: {req.get('id', '')})")
            if req.get("description"):
                ctx_lines.append(f"  Description: {req['description']}")
            if req.get("source"):
                ctx_lines.append(f"  Source: {req['source']}")
            if req.get("tags"):
                ctx_lines.append(f"  Tags: {', '.join(req['tags'])}")
            if req.get("release_id"):
                ctx_lines.append(f"  Release ID: {req['release_id']}")
            ctx_lines.append("")
    else:
        ctx_lines.append("Linked Requirements: none")
        ctx_lines.append("")

    # Linked releases (all fields)
    if releases_full:
        ctx_lines.append("=== LINKED RELEASES ===")
        for rel in releases_full:
            ctx_lines.append(f"Release: {rel.get('name', 'N/A')} (id: {rel.get('id', '')})")
            if rel.get("description"):
                ctx_lines.append(f"  Description: {rel['description']}")
            if rel.get("from_date"):
                ctx_lines.append(f"  From: {rel['from_date']}")
            if rel.get("to_date"):
                ctx_lines.append(f"  To: {rel['to_date']}")
            ctx_lines.append("")
    else:
        ctx_lines.append("Linked Releases: none")
        ctx_lines.append("")

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
) -> tuple[StructuredTestcase | None, int, str | None]:
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
            data = await _ollama_generate_request(client, prompt, timeout=90)
            text = (data.get("response") or data.get("output") or "").strip()
            text = _strip_markdown_code_fences(text)
            json_text = _extract_first_json_object(text) or text
            parsed = json.loads(json_text)
            tc = StructuredTestcase.model_validate(parsed)
            return tc, attempt, None
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
        except Exception as e:
            last_error = str(e)

    return None, 3, last_error


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
) -> tuple[GenerateTestSuiteResponse | None, int, str | None]:
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
            data = await _ollama_generate_request(client, prompt, timeout=120)
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

            return resp_model, attempt, None
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
        except Exception as e:
            last_error = str(e)

    return None, 3, last_error


async def generate_with_ollama(client: httpx.AsyncClient, requirement_title: str, requirement_desc: str | None, idx: int) -> str | None:
    prompt = (
        "You are a QA engineer. Generate a concise Gherkin scenario for this requirement. "
        "Include Given/When/Then steps only."
        f"\nRequirement: {requirement_title}\nDescription: {requirement_desc or 'N/A'}\n"
        f"Scenario index: {idx}\n"
    )
    try:
        data = await _ollama_generate_request(client, prompt, timeout=60)
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
        data = await _ollama_generate_request(client, prompt, timeout=120)
        text = (data.get("response") or data.get("output") or "").strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split('\n')
            # Remove first line (```javascript or similar)
            lines = lines[1:]
            # Remove last line if it's just ```
            if lines and lines[-1].strip() == "```":
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

        # IIFE: (async (page) => { ... })(page)
        m = re.search(
            r"async\s*\(\s*page\s*\)\s*=>\s*\{([\s\S]*?)\}\s*\)\s*\(\s*page\s*\)",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        # Non-IIFE arrow function: async (page) => { ... }  (no invocation)
        m = re.match(
            r"^\s*(?:const\s+\w+\s*=\s*)?async\s*\(\s*page\s*\)\s*=>\s*\{([\s\S]*)\}\s*;?\s*$",
            text,
            re.IGNORECASE,
        )
        if m:
            text = (m.group(1) or "").strip()
            continue

        # async function(page) { ... }  (no invocation)
        m = re.match(
            r"^\s*async\s+function\s*\(\s*page\s*\)\s*\{([\s\S]*)\}\s*;?\s*$",
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


async def _generate_playwright_script_single_call(
    client: httpx.AsyncClient,
    test_case_title: str,
    description: str,
    preconditions: str,
    steps,
    base_url_hint: str,
    context_text: str = "",
    kg: dict | None = None,
    gherkin: str = "",
) -> str | None:
    """Fast path: generate the entire Playwright script in a single LLM call.

    Uses the app knowledge graph so the LLM already knows every page's buttons,
    selectors, and routes — no live DOM snapshot needed.

    Returns the script string or *None* if the output looks broken.
    """
    steps_text = format_steps_for_mcp(steps)
    kg_block = _build_knowledge_graph_prompt_block(steps_text, kg=kg)

    prompt = "".join([
        "You are an expert Playwright automation engineer.\n",
        "Generate a COMPLETE Playwright script for ALL of the test steps below in ONE output.\n",
        "Output ONLY JavaScript code (no markdown, no code fences, no explanations).\n",
        "The code will be inserted inside `async (page) => { ... }` and executed via Playwright MCP.\n",
        "Only `page` is guaranteed to exist. Do NOT reference `context` or `browser`.\n",
        "Do NOT wrap your code in any function/IIFE.\n\n",
        "CRITICAL RULES:\n",
        "- Use page.getByRole(), page.getByText(), page.getByLabel(), page.locator() — NEVER page.evaluate().\n",
        "- SVG elements have no string className.\n",
        "- For navigation: await page.goto(url); await page.waitForLoadState('networkidle');\n",
        "- For clicks: await page.getByRole('button', {name:'Label'}).click();\n",
        "- For links: await page.getByRole('link', {name:'Label'}).click();\n",
        "- Add await page.waitForTimeout(500); after interactions that trigger navigation.\n",
        "- Prefer .first() when a selector may match multiple elements.\n\n",
        f"Docker base URL: {base_url_hint}\n",
        "Replace any localhost/127.0.0.1/0.0.0.0 URLs with the Docker base URL.\n\n",
        "=== APPLICATION KNOWLEDGE GRAPH ===\n",
        kg_block, "\n",
        "=== END KNOWLEDGE GRAPH ===\n\n",
        f"Test Case: {test_case_title}\n",
        f"Description: {description or 'N/A'}\n",
        f"Preconditions: {preconditions or 'N/A'}\n",
    ])
    if gherkin:
        prompt += f"\nGherkin/BDD Scenario:\n{gherkin}\n"
    prompt += "\n"
    if context_text:
        prompt += f"Additional context:\n{context_text[:2000]}\n\n"
    prompt += f"Steps to implement:\n{steps_text}\n\n"
    prompt += "Generate the COMPLETE script now."

    try:
        data = await _ollama_generate_request(client, prompt, timeout=120)
        text = (data.get("response") or data.get("output") or "").strip()
        text = _strip_markdown_code_fences(text)
        if not text or len(text) < 20:
            return None
        text = _unwrap_playwright_script_to_page_only(text)
        try:
            text = _URL_RE.sub(lambda m: rewrite_localhost_url(m.group(1)), text)
        except Exception:
            pass
        try:
            text = _rewrite_localhost_in_text(text)
        except Exception:
            pass
        return text.strip() or None
    except Exception:
        return None


async def generate_playwright_script_step_by_step_with_ollama(
    client: httpx.AsyncClient,
    test_case_title: str,
    description: str,
    preconditions: str,
    steps,
    base_url_hint: str,
    context_text: str = "",
    kg: dict | None = None,
    gherkin: str = "",
) -> tuple[str | None, str]:
    """Generate a Playwright script — fast single-call first, step-by-step fallback.

    1. **Fast path** (single LLM call with knowledge graph): ~10-15s
       Generates the complete script in one shot using the app knowledge graph
       for selector/route awareness. Used for most cases.
    2. **Step-by-step fallback**: Only used if fast path returns nothing.
       Iterates steps one-by-one with optional live DOM snapshots.

    Returns: (final_script_or_none, generation_log)
    """

    if not steps:
        return None, "No steps provided"

    if isinstance(steps, str):
        steps_list = [steps]
    elif isinstance(steps, list):
        steps_list = steps
    else:
        steps_list = [steps]

    log_lines: list[str] = []

    # ---- Fast path: single-call generation ----
    fast_script = await _generate_playwright_script_single_call(
        client, test_case_title, description, preconditions,
        steps, base_url_hint, context_text, kg=kg, gherkin=gherkin,
    )
    if fast_script:
        log_lines.append("Fast-path (single-call + knowledge graph): OK")
        return fast_script, "\n".join(log_lines)

    log_lines.append("Fast-path: failed, falling back to step-by-step")

    # ---- Step-by-step fallback ----
    current_script = ""

    context_text = (context_text or "").strip()
    if len(context_text) > 4000:
        context_text = context_text[:4000].rstrip() + "\n\n[Context truncated]"

    # Precompute the knowledge graph block once (scoped to the steps)
    steps_text_for_kg = format_steps_for_mcp(steps)
    kg_block = _build_knowledge_graph_prompt_block(steps_text_for_kg, kg=kg)

    for idx, step in enumerate(steps_list, start=1):
        action, expected = _format_step_for_llm(step, idx)
        if not action:
            continue

        context_block = ""
        if context_text:
            context_block = (
                "Context (may include app details, selectors, auth notes):\n"
                f"{context_text}\n\n"
            )

        # ---- Live DOM snapshot (lightweight, ~2s) ----
        dom_snapshot_block = ""
        if idx > 1 and current_script:
            try:
                snapshot = await _get_page_snapshot(client)
                if snapshot:
                    snap = snapshot[:3000]
                    dom_snapshot_block = (
                        "Live page element inventory (buttons, links, headings, inputs on current page):\n"
                        f"```\n{snap}\n```\n\n"
                    )
            except Exception:
                pass  # snapshot is optional

        prompt = "".join(
            [
                "You are an expert Playwright automation engineer. ",
                "We are building ONE Playwright script incrementally, one manual step at a time.\n\n",
                "Output ONLY JavaScript code (no markdown, no code fences, no explanations).\n",
                "The code will be inserted inside `async (page) => { ... }` and executed via Playwright MCP.\n",
                "Only `page` is guaranteed to exist. Do NOT reference `context` or `browser`.\n",
                "Do NOT wrap your code in any function/IIFE.\n\n",
                "CRITICAL RULES:\n",
                "- Use page.getByRole(), page.getByText(), page.getByLabel(), page.locator() — NEVER page.evaluate().\n",
                "- SVG elements have no string className.\n",
                "- Prefer .first() when a selector may match multiple elements.\n",
                "- Add short waits after navigation: await page.waitForLoadState('networkidle');\n\n",
                f"Docker base URL: {base_url_hint}\n",
                "Replace any localhost/127.0.0.1 URLs with the Docker base URL.\n\n",
                "=== APP KNOWLEDGE GRAPH (routes, buttons, selectors) ===\n",
                kg_block, "\n",
                "=== END KNOWLEDGE GRAPH ===\n\n",
                f"Test Case: {test_case_title}\n",
                f"Description: {description or 'N/A'}\n",
                f"Preconditions: {preconditions or 'N/A'}\n",
                f"Gherkin/BDD Scenario: {gherkin or 'N/A'}\n\n",
                context_block,
                dom_snapshot_block,
                "Current script so far (you MUST keep and extend it):\n",
                f"{current_script}\n\n",
                f"Now implement Step {idx}: {action}\n",
                f"Expected result: {expected or 'N/A'}\n\n",
                "Return the FULL updated script (including prior lines) as plain JavaScript code.",
            ]
        )

        try:
            data = await _ollama_generate_request(client, prompt, timeout=120)
            text = (data.get("response") or data.get("output") or "").strip()
            text = _strip_markdown_code_fences(text)
            if not text:
                log_lines.append(f"Step {idx}: empty model output")
                continue

            text = _unwrap_playwright_script_to_page_only(text)

            try:
                text = _URL_RE.sub(lambda m: rewrite_localhost_url(m.group(1)), text)
            except Exception:
                pass
            try:
                text = _rewrite_localhost_in_text(text)
            except Exception:
                pass

            current_script = text.strip()
            log_lines.append(f"Step {idx}: OK")
        except Exception as e:
            log_lines.append(f"Step {idx}: error: {e}")

    final_script = (current_script or "").strip()
    if not final_script:
        return None, "\n".join(log_lines) or "No script generated"
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
async def generate(payload: GenerateRequest, request: Request):
    async with httpx.AsyncClient(timeout=20, headers=_fwd_headers(request)) as client:
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
async def generate_structured_testcase(payload: GenerateStructuredRequest, request: Request):
    """Generate a single structured testcase for a requirement.

    Note: This endpoint does NOT persist the testcase; it only returns a validated JSON structure.
    """
    async with httpx.AsyncClient(timeout=30, headers=_fwd_headers(request)) as client:
        r = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Requirement not found")
        r.raise_for_status()
        req = r.json()

        tc, attempts, last_error = await generate_structured_testcase_with_ollama(
            client,
            requirement_title=req.get("title") or "Requirement",
            requirement_desc=req.get("description"),
        )
        if tc is None:
            # Fail fast: invalid LLM output (unable to produce a validated testcase)
            raise HTTPException(status_code=502, detail={"msg": "LLM output failed validation", "error": last_error})

        return {
            "testcase": tc,
            "generator": "ollama",
            "model": OLLAMA_MODEL,
            "attempts": attempts,
        }


@app.post("/generate-test-suite", response_model=GenerateTestSuiteResponse)
async def generate_test_suite(payload: GenerateTestSuiteRequest, request: Request):
    """Generate a structured test suite (positive + negative tests) for review.

    Note: This endpoint does NOT persist testcases.
    """
    async with httpx.AsyncClient(timeout=30, headers=_fwd_headers(request)) as client:
        r = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Requirement not found")
        r.raise_for_status()
        req = r.json()

        suite, attempts, last_error = await generate_test_suite_with_ollama(
            client,
            requirement_title=req.get("title") or "Requirement",
            requirement_desc=req.get("description"),
            positive_amount=payload.positive_amount,
            negative_amount=payload.negative_amount,
        )

        if suite is None:
            # Reject invalid LLM outputs so callers can handle/inspect the failure
            raise HTTPException(status_code=502, detail={"msg": "LLM output failed validation", "error": last_error})

        return suite.model_dump()

@app.post("/generate-automation-from-execution", response_model=ExecutionAutomationOut)
async def generate_automation_from_execution(payload: ExecutionGenerateRequest, request: Request):
    """Default: generate a script step-by-step (LLM), execute it, then persist the automation."""
    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
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
        gherkin = test_case.get("gherkin", "")
        metadata = test_case.get("metadata", {})
        description = metadata.get("description", "")
        preconditions = metadata.get("preconditions", "")
        steps = metadata.get("steps", [])

        context_text, context_meta = await _build_llm_execution_context(client, test_case)

        # Load knowledge graph from DB (falls back to hardcoded default)
        kg = await _load_knowledge_graph_for_app()

        script_outline, generation_log = await generate_playwright_script_step_by_step_with_ollama(
            client,
            test_case_title=title,
            description=description,
            preconditions=preconditions,
            steps=steps,
            base_url_hint=INTERNAL_FRONTEND_BASE_URL,
            context_text=context_text,
            kg=kg,
            gherkin=gherkin,
        )
        if not script_outline:
            script_outline = build_fallback_script_from_steps(steps)

        video_filename = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
        actions_taken = ""
        exec_success = False
        exec_error = None
        video_saved = False

        try:
            exec_data = await _execute_script_with_retries(client, script_outline, video_filename, record_video=True)
            exec_success = bool(exec_data.get("success"))
            actions_taken = exec_data.get("actions_taken") or exec_data.get("message") or ""
            exec_error = exec_data.get("error")
            video_saved = bool(exec_data.get("video_saved"))
        except Exception as e:
            exec_error = str(e)

        # Detect hidden errors in transcript even when MCP reports success
        hidden = _detect_hidden_errors(actions_taken, exec_error)
        if hidden and exec_success:
            exec_success = False
            exec_error = exec_error or hidden

        # If execution failed, try automatic repair attempts
        repair_attempts = 0
        repair_exec_data = None
        if not exec_success:
            try:
                repaired_script, repair_exec_data, repair_attempts = await _repair_and_rerun(
                    client,
                    script_outline,
                    video_filename,
                    test_case_id=payload.test_case_id,
                    exec_error=exec_error,
                    actions_taken=actions_taken,
                    context_text=context_text,
                    max_retries=2,
                    kg=kg,
                )
                if repair_exec_data:
                    exec_success = bool(repair_exec_data.get("success"))
                    actions_taken = repair_exec_data.get("actions_taken") or actions_taken
                    exec_error = repair_exec_data.get("error")
                    video_saved = bool(repair_exec_data.get("video_saved"))
                    # Re-check for hidden errors in repair output
                    repair_hidden = _detect_hidden_errors(actions_taken, exec_error)
                    if repair_hidden and exec_success:
                        exec_success = False
                        exec_error = exec_error or repair_hidden
                    # adopt repaired script for persistence if it succeeded
                    if exec_success:
                        script_outline = repaired_script
                # annotate generation metadata with repair results
                generation_metadata["repair_attempts"] = repair_attempts
                generation_metadata["repair_exec_data"] = repair_exec_data or {}
            except Exception:
                # swallow repair errors; keep original exec_error
                pass

        if exec_success:
            automation_status = "not_started"
            generation_note = f"Generated step-by-step via LLM and executed on {now_iso()}."
            notes_with_code = f"{generation_note}\n\nCode:\n{script_outline}" if script_outline else generation_note
            generation_metadata = {
                "generated_at": now_iso(),
                "model": OLLAMA_MODEL,
                "preconditions": preconditions,
                "video_filename": video_filename,
                "generation_mode": "step_by_step",
                "step_by_step_log": generation_log,
                "context": context_meta,
                "repair_attempts": repair_attempts,
                "repair_exec_data": repair_exec_data or {},
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
                "repair_attempts": repair_attempts,
                "repair_exec_data": repair_exec_data or {},
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
async def generate_automation_draft_from_execution(payload: ExecutionGenerateRequest, request: Request):
    """Default: generate a script step-by-step (LLM), then execute it, and return a reviewable automation draft (not persisted)."""
    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
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

        gherkin = test_case.get("gherkin", "")

        context_text, context_meta = await _build_llm_execution_context(client, test_case)

        # Load knowledge graph from DB (falls back to hardcoded default)
        kg = await _load_knowledge_graph_for_app()

        script_outline, generation_log = await generate_playwright_script_step_by_step_with_ollama(
            client,
            test_case_title=title,
            description=description,
            preconditions=preconditions,
            steps=steps,
            base_url_hint=INTERNAL_FRONTEND_BASE_URL,
            context_text=context_text,
            kg=kg,
            gherkin=gherkin,
        )
        if not script_outline:
            script_outline = build_fallback_script_from_steps(steps)

        video_filename = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
        exec_mode = "step_by_step"
        actions_taken = ""
        transcript_out: str | None = None
        exec_error = None
        exec_success = False
        video_saved = False

        try:
            exec_data = await _execute_script_with_retries(client, script_outline, video_filename, record_video=True)
            exec_success = bool(exec_data.get("success"))
            actions_taken = exec_data.get("actions_taken") or exec_data.get("message") or ""
            transcript_out = actions_taken
            exec_error = exec_data.get("error")
            video_saved = bool(exec_data.get("video_saved"))
        except Exception as e:
            exec_error = str(e)

        # Detect hidden errors in transcript even when MCP reports success
        hidden = _detect_hidden_errors(actions_taken, exec_error)
        if hidden and exec_success:
            exec_success = False
            exec_error = exec_error or hidden

        # Attempt automatic repair on failure
        repair_attempts = 0
        repair_exec_data = None
        if not exec_success:
            try:
                repaired_script, repair_exec_data, repair_attempts = await _repair_and_rerun(
                    client,
                    script_outline,
                    video_filename,
                    test_case_id=payload.test_case_id,
                    exec_error=exec_error,
                    actions_taken=actions_taken,
                    context_text=context_text,
                    max_retries=2,
                    kg=kg,
                )
                if repair_exec_data:
                    exec_success = bool(repair_exec_data.get("success"))
                    actions_taken = repair_exec_data.get("actions_taken") or actions_taken
                    transcript_out = actions_taken
                    exec_error = repair_exec_data.get("error")
                    video_saved = bool(repair_exec_data.get("video_saved"))
                    # Re-check for hidden errors in repair output
                    repair_hidden = _detect_hidden_errors(actions_taken, exec_error)
                    if repair_hidden and exec_success:
                        exec_success = False
                        exec_error = exec_error or repair_hidden
                    if exec_success:
                        script_outline = repaired_script
                generation_metadata["repair_attempts"] = repair_attempts
                generation_metadata["repair_exec_data"] = repair_exec_data or {}
            except Exception:
                pass

        notes = f"Generated step-by-step via LLM and executed on {now_iso()}."
        generation_metadata = {
            "generated_at": now_iso(),
            "model": OLLAMA_MODEL,
            "preconditions": preconditions,
            "video_filename": video_filename,
            "generation_mode": exec_mode,
            "step_by_step_log": generation_log,
            "context": context_meta,
            "repair_attempts": repair_attempts,
            "repair_exec_data": repair_exec_data or {},
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


@app.post("/automation-chat", response_model=AutomationChatResponse)
async def automation_chat(payload: AutomationChatRequest, request: Request):
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
        "Rules: reply is required. suggested_script is null or a full updated Playwright script body (no imports). "
        "If you include suggested_script, encode newlines as \\n inside the JSON string.\n\n"
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
                data = await _ollama_generate_request(
                    client,
                    prompt if not last_error else (prompt + f"\nFix your JSON. Error: {last_error}"),
                )
                text = (data.get("response") or data.get("output") or "").strip()
                last_text = text
                if not text:
                    raise ValueError("empty LLM response")
                text = _strip_markdown_code_fences(text)
                json_text = _extract_first_json_object(text) or text
                parsed = json.loads(json_text)
                out = AutomationChatResponse.model_validate(parsed)

                # If the model suggested an updated script, execute it and return video metadata
                suggested = (out.suggested_script or "").strip()
                if suggested:
                    video_filename_local = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
                    try:
                        exec_data = await _execute_script_with_retries(client, suggested, video_filename_local, record_video=True)
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
            except Exception as e:
                last_error = str(e)

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
                logger.warning("Failed to save automation: %s", e)

        return AutomationOut(
            title=payload.title,
            framework=framework,
            script_outline=automation_script,
            notes=f"Generated by {OLLAMA_MODEL} on {now_iso()}"
        )


@app.post("/push-test-to-git", tags=["generation"])
async def push_test_to_git_endpoint(payload: GitPushRequest, request: Request):
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
    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
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
                ssh_key_name=payload.ssh_key_name,
                auth_headers=_fwd_headers(request)
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

