"""
Generator Service v2 — LangChain + LangGraph powered.

Same API contract as v1 for drop-in compatibility.
Key changes:
  - All LLM calls go through LangChain's AzureChatOpenAI (llm.py)
  - Automation generation uses a LangGraph state graph (automation_graph.py)
  - Structured output uses Pydantic model validation via LangChain
  - CRUD endpoints (knowledge graphs, execute-script) are unchanged

New v2-only endpoints:
  GET /v2/graphs — list available LangGraph workflow graphs
"""

import os
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
import asyncio
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, ConfigDict, field_validator

from shared.db import get_db, close_client
from shared.models import GenerateRequest, GenerateResult, TestcaseOut
from shared.errors import setup_all_error_handlers
from shared.health import check_azure_llm, check_playwright_mcp, check_http_service, aggregate_health_status
from shared.settings import CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes

# LangChain integration
from llm import (
    llm_generate,
    llm_generate_json,
    llm_generate_structured,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    LLM_MODEL,
)
from automation_graph import AutomationState, get_automation_graph, build_automation_graph
from git_integration import push_test_to_git

logger = get_logger(__name__)

GIT_SERVICE_URL = os.getenv("GIT_SERVICE_URL", "http://git:8000")


def _fwd_headers(request: Request) -> dict:
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}


# ── Service URLs ─────────────────────────────────────────────────────────────
AUTOMATIONS_URL = os.getenv("AUTOMATIONS_SERVICE_URL", "http://automations:8000")
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp-agent:3000")
TC_URL = os.getenv("TESTCASES_SERVICE_URL", "http://testcases:8000")
REQ_URL = os.getenv("REQUIREMENTS_SERVICE_URL", "http://requirements:8000")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_SERVICE_URL", "http://orchestrator:8000")
INTERNAL_FRONTEND_BASE_URL = os.getenv("INTERNAL_FRONTEND_BASE_URL", "http://frontend:5173")
PLAYWRIGHT_MCP_CORE_URL = os.getenv("PLAYWRIGHT_MCP_CORE_URL", "http://playwright-mcp-core-1:8931/mcp")
PINCHTAB_URL = os.getenv("PINCHTAB_URL", "http://pinchtab:9867")


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_settings()
    setup_logging("generator-v2", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    db = get_db()
    await ensure_indexes(db, ["knowledge_graph"])
    logger.info("Generator v2 ready — LangChain + LangGraph engine")
    yield
    await close_client()


app = FastAPI(
    title="Generator Service v2",
    description="LangChain + LangGraph powered test and automation generation.",
    version="2.0.0",
    lifespan=lifespan,
)

setup_all_error_handlers(app)
setup_auth(app)
setup_rate_limiting(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════════════
# Pydantic models (same as v1)
# ═════════════════════════════════════════════════════════════════════════════

class StructuredStep(BaseModel):
    action: str
    expected_result: str


class StructuredTestcase(BaseModel):
    title: str
    description: str
    priority: str
    steps: list[StructuredStep]


class SuiteTestcase(BaseModel):
    title: str
    description: str
    priority: str
    steps: list[StructuredStep]
    test_type: str = "manual"


class GenerateStructuredRequest(BaseModel):
    requirement_id: str


class GenerateStructuredResponse(BaseModel):
    testcase_id: str
    title: str
    requirement_id: str
    model: str
    attempts: int


class GenerateTestSuiteRequest(BaseModel):
    requirement_id: str
    positive_amount: int = Field(3, ge=1, le=10)
    negative_amount: int = Field(2, ge=1, le=10)


class GenerateTestSuiteResponse(BaseModel):
    positive_tests: list[SuiteTestcase]
    negative_tests: list[SuiteTestcase]


class ExecutionGenerateRequest(BaseModel):
    test_case_id: str


class AutomationOut(BaseModel):
    automation_id: Optional[str] = None
    title: str = ""
    framework: str = "playwright"
    script_outline: Optional[str] = None
    notes: str = ""
    actions_taken: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AutomationDraftOut(BaseModel):
    title: str = ""
    framework: str = "playwright"
    script: Optional[str] = None
    exec_success: bool = False
    exec_error: Optional[str] = None
    transcript: Optional[str] = None
    video_filename: Optional[str] = None
    generation_log: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AutomationChatRequest(BaseModel):
    test_case_id: str
    message: str
    context: Optional[dict] = None
    history: Optional[list] = None


class AutomationChatResponse(BaseModel):
    reply: str
    suggested_script: Optional[str] = None
    exec_success: Optional[bool] = None
    exec_error: Optional[str] = None
    video_filename: Optional[str] = None
    video_path: Optional[str] = None


class AutomationGenerateRequest(BaseModel):
    test_case_id: str
    test_case_title: str = ""
    description: str = ""
    preconditions: str = ""
    steps: list = Field(default_factory=list)
    gherkin: str = ""
    context_text: str = ""


class KnowledgeGraphPageCreate(BaseModel):
    route: str
    description: str = ""
    key_buttons: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    dialogs: list[str] = Field(default_factory=list)
    empty_state: str = ""
    also: str = ""
    interactive: str = ""
    sections: list[str] = Field(default_factory=list)
    form_fields: list[str] = Field(default_factory=list)
    tabs: list[str] = Field(default_factory=list)


class KnowledgeGraphNavItem(BaseModel):
    label: str
    route: str


class KnowledgeGraphCreate(BaseModel):
    app_name: str
    framework: str = ""
    base_url: str = ""
    selector_strategy: str = ""
    nav_items: list[KnowledgeGraphNavItem] = Field(default_factory=list)
    pages: list[KnowledgeGraphPageCreate] = Field(default_factory=list)
    common_button_labels: list[str] = Field(default_factory=list)
    aria_labels: list[str] = Field(default_factory=list)
    is_default: bool = False


class KnowledgeGraphUpdate(BaseModel):
    app_name: Optional[str] = None
    framework: Optional[str] = None
    base_url: Optional[str] = None
    selector_strategy: Optional[str] = None
    nav_items: Optional[list[KnowledgeGraphNavItem]] = None
    pages: Optional[list[KnowledgeGraphPageCreate]] = None
    common_button_labels: Optional[list[str]] = None
    aria_labels: Optional[list[str]] = None
    is_default: Optional[bool] = None


class KGAnalyzeRequest(BaseModel):
    app_name: str
    framework: str = ""
    base_url: str


class PushTestToGitRequest(BaseModel):
    test_case_id: str
    title: str
    script: str
    repo_connection_id: Optional[str] = None
    provider: Optional[Literal["github", "gitlab", "azure"]] = None
    repo_url: Optional[str] = None
    base_branch: Optional[str] = None
    ssh_key_name: Optional[str] = None
    api_token_id: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_MARKDOWN_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_markdown_code_fences(text: str) -> str:
    text = _MARKDOWN_FENCE_RE.sub("", text)
    text = _MARKDOWN_FENCE_END_RE.sub("", text)
    return text.strip()


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None


async def _load_knowledge_graph_for_app(app_name: str | None = None) -> dict | None:
    """Load KG from MongoDB (defaults to the is_default=True one)."""
    db = get_db()
    col = db["knowledge_graph"]
    if app_name:
        doc = await col.find_one({"app_name": app_name})
    else:
        doc = await col.find_one({"is_default": True})
    if not doc:
        doc = await col.find_one()
    if doc:
        doc.pop("_id", None)
        return doc
    return None


def _build_knowledge_graph_prompt_block(steps_text: str = "", kg: dict | None = None) -> str:
    """Build a prompt block from a KG dict for injection into LLM prompts."""
    if not kg:
        return ""
    lines = [f"App: {kg.get('app_name', 'Unknown')}"]
    lines.append(f"Framework: {kg.get('framework', 'Unknown')}")
    lines.append(f"Base URL: {kg.get('base_url', '')}")
    if kg.get("selector_strategy"):
        lines.append(f"Selector strategy: {kg['selector_strategy']}")
    if kg.get("nav_items"):
        lines.append("Navigation:")
        for ni in kg["nav_items"]:
            lines.append(f"  - {ni.get('label', '')} → {ni.get('route', '')}")
    if kg.get("pages"):
        lines.append("Pages:")
        for p in kg["pages"]:
            lines.append(f"  {p.get('route', '/')}:")
            if p.get("description"):
                lines.append(f"    Description: {p['description']}")
            if p.get("key_buttons"):
                lines.append(f"    Buttons: {', '.join(p['key_buttons'])}")
            if p.get("filters"):
                lines.append(f"    Filters: {', '.join(p['filters'])}")
            if p.get("dialogs"):
                lines.append(f"    Dialogs: {', '.join(p['dialogs'])}")
    return "\n".join(lines)


async def _fetch_memory_prompt_block(client: httpx.AsyncClient, page: str | None = None) -> str:
    try:
        params = {}
        if page:
            params["page"] = page
        resp = await client.get(f"{ORCHESTRATOR_URL}/memory/prompt-block", params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json().get("prompt_block", "")
    except Exception:
        pass
    return ""


async def _report_outcome_to_orchestrator(client: httpx.AsyncClient, **kwargs) -> None:
    try:
        await client.post(
            f"{ORCHESTRATOR_URL}/memory/record-outcome",
            json={"model": LLM_MODEL, **kwargs},
            timeout=5,
        )
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
# Knowledge Graph CRUD (unchanged from v1)
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/knowledge-graphs", tags=["knowledge-graph"])
async def list_knowledge_graphs():
    db = get_db()
    cursor = db["knowledge_graph"].find().sort("app_name", 1)
    results = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        results.append(doc)
    return results


@app.get("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def get_knowledge_graph(kg_id: str):
    db = get_db()
    doc = await db["knowledge_graph"].find_one({"_id": ObjectId(kg_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.post("/knowledge-graphs", tags=["knowledge-graph"], status_code=201)
async def create_knowledge_graph(body: KnowledgeGraphCreate):
    db = get_db()
    data = body.model_dump()
    data["created_at"] = datetime.now(timezone.utc)
    data["updated_at"] = data["created_at"]
    if data.get("is_default"):
        await db["knowledge_graph"].update_many({"is_default": True}, {"$set": {"is_default": False}})
    result = await db["knowledge_graph"].insert_one(data)
    data["id"] = str(result.inserted_id)
    data.pop("_id", None)
    return data


@app.put("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def update_knowledge_graph(kg_id: str, body: KnowledgeGraphUpdate):
    db = get_db()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    update_data["updated_at"] = datetime.now(timezone.utc)
    if update_data.get("is_default"):
        await db["knowledge_graph"].update_many(
            {"is_default": True, "_id": {"$ne": ObjectId(kg_id)}},
            {"$set": {"is_default": False}},
        )
    result = await db["knowledge_graph"].update_one(
        {"_id": ObjectId(kg_id)}, {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    doc = await db["knowledge_graph"].find_one({"_id": ObjectId(kg_id)})
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.delete("/knowledge-graphs/{kg_id}", tags=["knowledge-graph"])
async def delete_knowledge_graph(kg_id: str):
    db = get_db()
    result = await db["knowledge_graph"].delete_one({"_id": ObjectId(kg_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    return {"status": "deleted"}


# ═════════════════════════════════════════════════════════════════════════════
# KG Analysis (PinchTab + LangChain)
# ═════════════════════════════════════════════════════════════════════════════

async def _pinchtab_start_instance(client: httpx.AsyncClient) -> str:
    """Start a headless PinchTab browser instance and return the instance ID."""
    resp = await client.post(
        f"{PINCHTAB_URL}/instances/start",
        json={"mode": "headless"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    inst_id = data.get("id", "")
    logger.info(f"PinchTab instance started: {inst_id}")
    # Wait for instance to be ready
    for _ in range(10):
        await asyncio.sleep(1)
        try:
            check = await client.get(f"{PINCHTAB_URL}/instances/{inst_id}", timeout=5)
            if check.status_code == 200 and check.json().get("status") == "running":
                break
        except Exception:
            pass
    return inst_id


async def _pinchtab_open_tab(client: httpx.AsyncClient, instance_id: str, url: str) -> str:
    """Open a new tab in the PinchTab instance and return the tab ID."""
    resp = await client.post(
        f"{PINCHTAB_URL}/instances/{instance_id}/tabs/open",
        json={"url": url},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("tabId", "")


async def _pinchtab_snapshot(client: httpx.AsyncClient, tab_id: str) -> dict:
    """Get the accessibility tree snapshot from a PinchTab tab."""
    resp = await client.get(
        f"{PINCHTAB_URL}/tabs/{tab_id}/snapshot",
        params={"filter": "interactive"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def _pinchtab_text(client: httpx.AsyncClient, tab_id: str) -> dict:
    """Get the text content from a PinchTab tab."""
    resp = await client.get(
        f"{PINCHTAB_URL}/tabs/{tab_id}/text",
        params={"mode": "raw"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def _pinchtab_close_tab(client: httpx.AsyncClient, tab_id: str) -> None:
    """Close a PinchTab tab."""
    try:
        await client.delete(f"{PINCHTAB_URL}/tabs/{tab_id}", timeout=10)
    except Exception:
        pass


async def _pinchtab_stop_instance(client: httpx.AsyncClient, instance_id: str) -> None:
    """Stop a PinchTab browser instance."""
    try:
        await client.post(f"{PINCHTAB_URL}/instances/{instance_id}/stop", timeout=10)
    except Exception:
        pass


async def _pinchtab_snapshot_page(client: httpx.AsyncClient, instance_id: str, url: str) -> dict:
    """Navigate to a URL via PinchTab, take a snapshot, return page data."""
    try:
        tab_id = await _pinchtab_open_tab(client, instance_id, url)
        await asyncio.sleep(2)  # Wait for page to load

        snapshot_data = await _pinchtab_snapshot(client, tab_id)
        text_data = await _pinchtab_text(client, tab_id)

        # Format snapshot nodes as readable text
        nodes = snapshot_data.get("nodes", [])
        snapshot_lines = []
        for node in nodes:
            ref = node.get("ref", "")
            role = node.get("role", "")
            name = node.get("name", "")
            snapshot_lines.append(f"[{ref}] {role}: {name}")
        snapshot_text = "\n".join(snapshot_lines)

        await _pinchtab_close_tab(client, tab_id)

        return {
            "url": url,
            "snapshot": snapshot_text,
            "text": text_data.get("text", ""),
            "title": text_data.get("title", snapshot_data.get("title", "")),
            "nodes": nodes,
        }
    except Exception as e:
        logger.warning(f"PinchTab snapshot failed for {url}: {e}")
        return {"url": url, "snapshot": "", "text": "", "error": str(e), "nodes": []}


def _rewrite_url_for_docker(url: str) -> str:
    """Rewrite localhost URLs so the Playwright MCP container can reach them."""
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(url)
    if parsed.hostname in ("localhost", "127.0.0.1"):
        # Map well-known host ports to Docker service names
        port = parsed.port
        host_map = {
            5173: "frontend",
        }
        new_host = host_map.get(port)
        if new_host:
            # Service listens on the same port inside Docker
            parsed = parsed._replace(netloc=f"{new_host}:{port}")
        else:
            # Fallback: try host.docker.internal
            parsed = parsed._replace(netloc=f"host.docker.internal:{port}" if port else "host.docker.internal")
        return urlunparse(parsed)
    return url


def _sanitize_kg_analysis(parsed: dict) -> dict:
    """Coerce raw LLM JSON output to match KnowledgeGraphCreate schema types."""
    result = {}

    # selector_strategy must be a string
    ss = parsed.get("selector_strategy", "")
    if isinstance(ss, dict):
        result["selector_strategy"] = json.dumps(ss)
    elif isinstance(ss, list):
        result["selector_strategy"] = ", ".join(str(s) for s in ss)
    else:
        result["selector_strategy"] = str(ss) if ss else ""

    # nav_items: list of {label, route}
    nav = parsed.get("nav_items", [])
    if isinstance(nav, list):
        result["nav_items"] = [
            {"label": str(ni.get("label", "") if isinstance(ni, dict) else ni),
             "route": str(ni.get("route", "") if isinstance(ni, dict) else "")}
            for ni in nav
        ]
    else:
        result["nav_items"] = []

    # pages: list of page objects, coerce all fields to correct types
    pages = parsed.get("pages", [])
    if isinstance(pages, list):
        sanitized_pages = []
        for p in pages:
            if not isinstance(p, dict):
                continue
            sanitized_pages.append({
                "route": str(p.get("route", "")),
                "description": str(p.get("description", "")),
                "key_buttons": [str(b) for b in p.get("key_buttons", [])] if isinstance(p.get("key_buttons"), list) else [],
                "filters": [str(f) for f in p.get("filters", [])] if isinstance(p.get("filters"), list) else [],
                "dialogs": [str(d) for d in p.get("dialogs", [])] if isinstance(p.get("dialogs"), list) else [],
            })
        result["pages"] = sanitized_pages
    else:
        result["pages"] = []

    # common_button_labels: list of strings
    cbl = parsed.get("common_button_labels", [])
    if isinstance(cbl, list):
        result["common_button_labels"] = [str(b) for b in cbl]
    else:
        result["common_button_labels"] = []

    # aria_labels: list of strings
    al = parsed.get("aria_labels", [])
    if isinstance(al, list):
        result["aria_labels"] = [str(a) for a in al]
    else:
        result["aria_labels"] = []

    return result


@app.post("/knowledge-graphs/analyze", tags=["knowledge-graph"])
async def analyze_for_knowledge_graph(body: KGAnalyzeRequest):
    """Use PinchTab + LangChain to crawl and extract KG from accessibility tree."""
    from urllib.parse import urljoin
    original_base = body.base_url.rstrip("/")
    base = _rewrite_url_for_docker(original_base)

    async with httpx.AsyncClient() as client:
        # Start a PinchTab browser instance
        try:
            instance_id = await _pinchtab_start_instance(client)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"PinchTab instance start failed: {e}")

        try:
            landing = await _pinchtab_snapshot_page(client, instance_id, base)

            # Use LangChain to extract links from the accessibility snapshot
            link_prompt = (
                f"From this web page accessibility tree snapshot, extract ALL internal navigation links.\n"
                f"Base URL: {original_base}\n\n"
                f"--- ACCESSIBILITY TREE ---\n{landing['snapshot'][:6000]}\n"
                f"--- PAGE TEXT ---\n{landing['text'][:3000]}\n---\n\n"
                f"Return ONLY a JSON array of absolute URLs. Example: [\"{original_base}\", \"{original_base}/page1\"]"
            )
            try:
                link_result = await llm_generate(link_prompt, timeout=60)
                cleaned = _strip_markdown_code_fences(link_result)
                discovered_urls = json.loads(cleaned)
                if not isinstance(discovered_urls, list):
                    discovered_urls = [original_base]
            except Exception:
                discovered_urls = [original_base]

            seen = set()
            unique_urls = []
            for u in discovered_urls:
                resolved = urljoin(original_base + "/", u).rstrip("/")
                if resolved not in seen:
                    seen.add(resolved)
                    unique_urls.append(resolved)
            unique_urls = unique_urls[:20]

            all_snapshots = []
            for page_url in unique_urls:
                if page_url.rstrip("/") == original_base:
                    all_snapshots.append(landing)
                else:
                    # Rewrite each discovered URL for Docker access
                    docker_url = _rewrite_url_for_docker(page_url)
                    snap = await _pinchtab_snapshot_page(client, instance_id, docker_url)
                    # Store the original URL for display
                    snap["display_url"] = page_url
                    all_snapshots.append(snap)
        finally:
            await _pinchtab_stop_instance(client, instance_id)

        # Build combined context and use LangChain for extraction
        pages_context = ""
        for i, snap in enumerate(all_snapshots):
            if snap.get("error") and not snap["snapshot"]:
                continue
            display_url = snap.get("display_url") or snap['url'].replace(base, original_base) if base != original_base else snap['url']
            pages_context += f"\n===== PAGE {i+1}: {display_url} =====\n"
            pages_context += f"--- Accessibility Tree ---\n{snap['snapshot'][:3000]}\n"
            pages_context += f"--- Page Text ---\n{snap['text'][:1500]}\n"

        analysis_prompt = (
            f"Analyze these {len(all_snapshots)} page accessibility tree snapshots and extract a knowledge graph.\n"
            f"App: {body.app_name}, Framework: {body.framework}, Base URL: {body.base_url}\n\n"
            f"{pages_context[:25000]}\n\n"
            "Return JSON with: selector_strategy, nav_items[{label,route}], "
            "pages[{route,description,key_buttons,filters,dialogs}], "
            "common_button_labels[], aria_labels[]"
        )

        try:
            parsed = await llm_generate_json(analysis_prompt, timeout=180)
            # Sanitize LLM output to match KnowledgeGraphCreate schema
            sanitized = _sanitize_kg_analysis(parsed)
            return {"app_name": body.app_name, "framework": body.framework,
                    "base_url": original_base, "pages_crawled": len(all_snapshots), **sanitized}
        except json.JSONDecodeError:
            raw = await llm_generate(analysis_prompt, timeout=180)
            return {"app_name": body.app_name, "framework": body.framework,
                    "base_url": original_base, "pages_crawled": len(all_snapshots),
                    "raw_analysis": raw, "nav_items": [], "pages": []}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"LLM analysis failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# Generate test cases (LangChain)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/generate-structured-testcase", tags=["generation"])
async def generate_structured_testcase(payload: GenerateStructuredRequest, request: Request):
    """Generate a structured test case using Azure OpenAI."""
    async with httpx.AsyncClient(timeout=60, headers=_fwd_headers(request)) as client:
        req_resp = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if req_resp.status_code != 200:
            raise HTTPException(status_code=req_resp.status_code, detail="Requirement not found")
        requirement = req_resp.json()

    title = requirement.get("title", "")
    desc = requirement.get("description", "")

    schema_hint = '{"title":"...","description":"...","priority":"critical|high|medium|low","steps":[{"action":"...","expected_result":"..."}]}'
    prompt = (
        "You are a QA engineer. Generate exactly ONE manual test case.\n"
        f"Output JSON matching: {schema_hint}\n"
        f"Requirement: {title}\nDescription: {desc or 'N/A'}\n"
    )

    tc = await llm_generate_structured(prompt, StructuredTestcase, timeout=90)

    # Convert structured steps to Gherkin format
    gherkin_lines = [f"Feature: {tc.title}", "", f"  Scenario: {tc.title}"]
    for step in tc.steps:
        gherkin_lines.append(f"    When {step.action}")
        gherkin_lines.append(f"    Then {step.expected_result}")
    gherkin_text = "\n".join(gherkin_lines)

    # Save to testcases service
    tc_data = {
        "title": tc.title,
        "gherkin": gherkin_text,
        "requirement_id": payload.requirement_id,
        "status": "draft",
        "metadata": {
            "description": tc.description,
            "priority": tc.priority,
            "test_type": "manual",
            "preconditions": "",
            "steps": [s.model_dump() for s in tc.steps],
        },
        "review_status": "pending_review",
    }

    async with httpx.AsyncClient(timeout=30, headers=_fwd_headers(request)) as client:
        save_resp = await client.post(f"{TC_URL}/testcases", json=tc_data)
        save_resp.raise_for_status()
        saved = save_resp.json()

    return GenerateStructuredResponse(
        testcase_id=saved.get("id", ""),
        title=tc.title,
        requirement_id=payload.requirement_id,
        model=LLM_MODEL,
        attempts=1,
    )


@app.post("/generate-test-suite", tags=["generation"])
async def generate_test_suite(payload: GenerateTestSuiteRequest, request: Request):
    """Generate a test suite using Azure OpenAI."""
    async with httpx.AsyncClient(timeout=60, headers=_fwd_headers(request)) as client:
        req_resp = await client.get(f"{REQ_URL}/requirements/{payload.requirement_id}")
        if req_resp.status_code != 200:
            raise HTTPException(status_code=req_resp.status_code, detail="Requirement not found")
        requirement = req_resp.json()

    title = requirement.get("title", "")
    desc = requirement.get("description", "")

    prompt = (
        "You are a QA engineer. Generate a test suite.\n"
        f"Generate {payload.positive_amount} positive_tests and {payload.negative_amount} negative_tests.\n"
        "Each test: title, description, priority (critical|high|medium|low), steps [{action, expected_result}].\n"
        'Return JSON: {"positive_tests":[...],"negative_tests":[...]}\n\n'
        f"Requirement: {title}\nDescription: {desc or 'N/A'}\n"
    )

    result = await llm_generate_structured(prompt, GenerateTestSuiteResponse, timeout=120)

    # Save each test case
    saved_ids = {"positive": [], "negative": []}
    async with httpx.AsyncClient(timeout=30, headers=_fwd_headers(request)) as client:
        for category, tests in [("positive", result.positive_tests), ("negative", result.negative_tests)]:
            for tc in tests:
                gherkin_lines = [f"Feature: {tc.title}", "", f"  Scenario: {tc.title}"]
                for step in tc.steps:
                    gherkin_lines.append(f"    When {step.action}")
                    gherkin_lines.append(f"    Then {step.expected_result}")
                gherkin_text = "\n".join(gherkin_lines)
                tc_data = {
                    "title": tc.title,
                    "gherkin": gherkin_text,
                    "requirement_id": payload.requirement_id,
                    "status": "draft",
                    "metadata": {
                        "description": tc.description,
                        "priority": tc.priority,
                        "test_type": "manual",
                        "category": category,
                        "preconditions": "",
                        "steps": [s.model_dump() for s in tc.steps],
                    },
                    "review_status": "pending_review",
                }
                try:
                    save_resp = await client.post(f"{TC_URL}/testcases", json=tc_data)
                    save_resp.raise_for_status()
                    saved = save_resp.json()
                    saved_ids[category].append(saved.get("id", ""))
                except Exception as e:
                    logger.warning(f"Failed to save suite test case: {e}")

    return {
        "requirement_id": payload.requirement_id,
        "model": LLM_MODEL,
        "positive_tests": [t.model_dump() for t in result.positive_tests],
        "negative_tests": [t.model_dump() for t in result.negative_tests],
        "positive_count": len(result.positive_tests),
        "negative_count": len(result.negative_tests),
        "saved_ids": saved_ids,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Generate Automation (LangGraph pipeline)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/generate-automation-from-execution", tags=["generation"])
async def generate_automation_from_execution(payload: ExecutionGenerateRequest, request: Request):
    """Generate, execute, and auto-repair automation via LangGraph pipeline."""
    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
        tc_resp = await client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
        if tc_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Test case not found")
        tc_resp.raise_for_status()
        test_case = tc_resp.json()

        title = test_case.get("title", "Automation")
        metadata = test_case.get("metadata", {})
        kg, memory_block = await asyncio.gather(
            _load_knowledge_graph_for_app(),
            _fetch_memory_prompt_block(client),
        )
        kg_block = _build_knowledge_graph_prompt_block(kg=kg) if kg else ""

        # Run the LangGraph automation pipeline
        graph = get_automation_graph()
        initial = AutomationState(
            test_case_id=payload.test_case_id,
            test_case_title=title,
            description=metadata.get("description", ""),
            preconditions=metadata.get("preconditions", ""),
            steps=metadata.get("steps", []),
            gherkin=test_case.get("gherkin", ""),
            base_url=INTERNAL_FRONTEND_BASE_URL,
            kg_block=kg_block,
            memory_block=memory_block,
            playwright_mcp_url=PLAYWRIGHT_MCP_URL,
            auth_headers=_fwd_headers(request),
        )

        final = await graph.ainvoke(initial)
        s = final if isinstance(final, dict) else final.__dict__

        script = s.get("script", "")
        exec_success = s.get("exec_success", False)
        exec_error = s.get("exec_error", "")
        actions_taken = s.get("actions_taken", "")
        repair_attempts = s.get("repair_attempts", 0)
        video_filename = s.get("video_filename", "")
        video_saved = s.get("video_saved", False)
        gen_log = "\n".join(s.get("generation_log", []))

        automation_status = "passing" if exec_success else "failing"
        automation_data = {
            "test_case_id": payload.test_case_id,
            "title": title,
            "framework": "playwright",
            "script": script,
            "status": automation_status,
            "notes": f"Generated via LangGraph v2 pipeline\n{gen_log}",
            "last_actions": actions_taken,
            "metadata": {
                "engine": "langgraph",
                "model": LLM_MODEL,
                "repair_attempts": repair_attempts,
                "exec_success": exec_success,
            },
        }
        if video_saved:
            automation_data["video_path"] = f"/videos/{video_filename}"

        save_resp = await client.post(f"{AUTOMATIONS_URL}/automations", json=automation_data)
        save_resp.raise_for_status()
        saved = save_resp.json()

        await _report_outcome_to_orchestrator(
            client,
            test_case_id=payload.test_case_id,
            requirement_id=test_case.get("requirement_id"),
            first_try_success=exec_success and repair_attempts == 0,
            repair_attempts=repair_attempts,
            final_success=exec_success,
            error_type=exec_error[:200] if exec_error and not exec_success else None,
            generation_mode="langgraph",
        )

        return AutomationOut(
            automation_id=saved.get("id"),
            title=title,
            framework="playwright",
            script_outline=script,
            notes=gen_log,
            actions_taken=actions_taken,
            prompt_tokens=s.get("prompt_tokens", 0),
            completion_tokens=s.get("completion_tokens", 0),
            total_tokens=s.get("total_tokens", 0),
        )


@app.post("/generate-automation-draft-from-execution", tags=["generation"])
async def generate_automation_draft(payload: ExecutionGenerateRequest, request: Request):
    """Generate a draft automation via LangGraph (reviewable, not persisted)."""
    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
        tc_resp = await client.get(f"{TC_URL}/testcases/{payload.test_case_id}")
        if tc_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Test case not found")
        tc_resp.raise_for_status()
        test_case = tc_resp.json()

        metadata = test_case.get("metadata", {})
        kg, memory_block = await asyncio.gather(
            _load_knowledge_graph_for_app(),
            _fetch_memory_prompt_block(client),
        )
        kg_block = _build_knowledge_graph_prompt_block(kg=kg) if kg else ""

        graph = get_automation_graph()
        initial = AutomationState(
            test_case_id=payload.test_case_id,
            test_case_title=test_case.get("title", ""),
            description=metadata.get("description", ""),
            preconditions=metadata.get("preconditions", ""),
            steps=metadata.get("steps", []),
            gherkin=test_case.get("gherkin", ""),
            base_url=INTERNAL_FRONTEND_BASE_URL,
            kg_block=kg_block,
            memory_block=memory_block,
            playwright_mcp_url=PLAYWRIGHT_MCP_URL,
            auth_headers=_fwd_headers(request),
        )

        final = await graph.ainvoke(initial)
        s = final if isinstance(final, dict) else final.__dict__

        return AutomationDraftOut(
            title=test_case.get("title", ""),
            framework="playwright",
            script=s.get("script"),
            exec_success=s.get("exec_success", False),
            exec_error=s.get("exec_error"),
            transcript=s.get("actions_taken"),
            video_filename=s.get("video_filename"),
            generation_log="\n".join(s.get("generation_log", [])),
            prompt_tokens=s.get("prompt_tokens", 0),
            completion_tokens=s.get("completion_tokens", 0),
            total_tokens=s.get("total_tokens", 0),
        )


# ═════════════════════════════════════════════════════════════════════════════
# Automation Chat (LangChain)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/automation-chat", response_model=AutomationChatResponse, tags=["generation"])
async def automation_chat(payload: AutomationChatRequest, request: Request):
    """Chat about an automation draft using LangChain."""
    context = payload.context or {}
    current_script = (context.get("current_script") or "").strip()
    actions_taken = (context.get("actions_taken") or "").strip()
    exec_error = (context.get("exec_error") or "").strip()

    history = payload.history or []
    history_lines = []
    for item in history[-10:]:
        if isinstance(item, dict):
            history_lines.append(f"- {item.get('role', 'user')}: {item.get('content', '')}")

    prompt = (
        "You are an automation engineer helping review a Playwright draft.\n"
        'Return JSON: {"reply":"...","suggested_script":null}\n'
        "suggested_script is null or a full updated script body.\n\n"
        f"Test case: {payload.test_case_id}\n"
        f"Error: {exec_error or 'N/A'}\n"
        f"Script:\n{current_script or 'N/A'}\n\n"
        f"History:\n" + ("\n".join(history_lines) or "N/A") + "\n\n"
        f"User: {payload.message}\n"
    )

    try:
        parsed = await llm_generate_json(prompt, timeout=60)
        out = AutomationChatResponse.model_validate(parsed)

        if out.suggested_script and out.suggested_script.strip():
            from automation_graph import ROUTE_PREFIX, _rewrite_localhost_urls
            prepared = ROUTE_PREFIX + _rewrite_localhost_urls(out.suggested_script)
            video_fn = f"{payload.test_case_id}_{int(datetime.now(timezone.utc).timestamp())}.webm"
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    exec_resp = await client.post(
                        f"{PLAYWRIGHT_MCP_URL}/execute",
                        json={"script": prepared, "video_path": video_fn, "record_video": True},
                        timeout=120,
                    )
                    exec_data = exec_resp.json()
                    out.exec_success = bool(exec_data.get("success"))
                    out.exec_error = exec_data.get("error")
                    if out.exec_success and exec_data.get("video_saved"):
                        out.video_filename = video_fn
                        out.video_path = f"/videos/{video_fn}"
            except Exception as e:
                out.exec_success = False
                out.exec_error = str(e)

        return out
    except Exception:
        reply = await llm_generate(prompt, timeout=60)
        return AutomationChatResponse(reply=reply.strip() or "I couldn't generate a response.", suggested_script=None)


# ═════════════════════════════════════════════════════════════════════════════
# Simple generate (legacy compat)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/generate-automation", tags=["generation"])
async def generate_automation(payload: AutomationGenerateRequest):
    """Simple one-shot automation generation via LangChain (no execution)."""
    kg = await _load_knowledge_graph_for_app()
    kg_block = _build_knowledge_graph_prompt_block(kg=kg) if kg else ""

    steps_text = "\n".join(
        f"Step {i+1}: {s.get('action','') if isinstance(s,dict) else s}"
        for i, s in enumerate(payload.steps)
    )

    prompt = (
        "Generate a Playwright script body (JS, no imports, no function wrapper).\n"
        "Runs inside `async (page) => { ... }`.\n"
        "User is ALREADY logged in. NO login code.\n\n"
        f"Test: {payload.test_case_title}\n"
        f"Description: {payload.description or 'N/A'}\n"
        f"Steps:\n{steps_text}\n"
    )
    if kg_block:
        prompt += f"\n=== KNOWLEDGE GRAPH ===\n{kg_block}\n=== END ===\n"
    if payload.gherkin:
        prompt += f"\nGherkin:\n{payload.gherkin}\n"

    script = await llm_generate(prompt, timeout=120)
    script = _strip_markdown_code_fences(script)

    return {"script": script, "model": LLM_MODEL}


# ═════════════════════════════════════════════════════════════════════════════
# Execute script (proxy to Playwright MCP - unchanged)
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/execute-script", tags=["execution"])
async def execute_script(payload: dict):
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{PLAYWRIGHT_MCP_URL}/execute", json=payload, timeout=120)
        return resp.json()


@app.post("/execute-script-debug", tags=["execution"])
async def execute_script_debug(payload: dict):
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{PLAYWRIGHT_MCP_URL}/execute", json=payload, timeout=120)
        return resp.json()


# ═════════════════════════════════════════════════════════════════════════════
# Git integration: push test to repo
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/push-test-to-git", tags=["git"])
async def push_test_to_git_endpoint(payload: PushTestToGitRequest, request: Request):
    """Push a saved automation script to the linked test repository and create a PR."""
    repo_url = payload.repo_url
    provider = payload.provider
    base_branch = payload.base_branch
    ssh_key_name = payload.ssh_key_name
    repo_path = None
    api_token_id = payload.api_token_id

    # If a repo_connection_id is provided, look up repo details from the git service
    if payload.repo_connection_id:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{GIT_SERVICE_URL}/repo-connections")
                resp.raise_for_status()
                connections = resp.json()
                conn = next(
                    (c for c in connections if c.get("id") == payload.repo_connection_id),
                    None,
                )
                if not conn:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Repo connection {payload.repo_connection_id} not found",
                    )
                repo_url = repo_url or conn.get("repo_url")
                provider = provider or conn.get("provider")
                base_branch = base_branch or conn.get("branch") or "main"
                ssh_key_name = ssh_key_name or conn.get("ssh_key_name")
                repo_path = conn.get("repo_path")
                api_token_id = api_token_id or conn.get("api_token_id")
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch repo connection from git service: {exc}",
            )

    if not repo_url and not repo_path:
        raise HTTPException(
            status_code=400,
            detail="No repo_url provided and no repo connection found. "
                   "Please connect a test repository first.",
        )

    if not provider:
        raise HTTPException(
            status_code=400, detail="Git provider could not be determined."
        )

    # Map provider names (repo connections use 'azureDevOps', push_test_to_git expects 'azure')
    provider_map = {"azureDevOps": "azure", "github": "github", "gitlab": "gitlab"}
    mapped_provider = provider_map.get(provider, provider)
    if mapped_provider not in ("github", "gitlab", "azure"):
        raise HTTPException(status_code=400, detail=f"Unsupported git provider: {provider}")

    try:
        result = await push_test_to_git(
            test_case_id=payload.test_case_id,
            test_title=payload.title,
            script_content=payload.script,
            provider=mapped_provider,
            repo_url=repo_url,
            base_branch=base_branch or "main",
            ssh_key_name=ssh_key_name,
            auth_headers=_fwd_headers(request),
            repo_path=repo_path,
            api_token_id=api_token_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        logger.error("Git push failed: %s — %s", exc.response.status_code, exc.response.text)
        raise HTTPException(
            status_code=502,
            detail=f"Git operation failed: {exc.response.text}",
        )
    except Exception as exc:
        logger.exception("Unexpected error pushing test to git")
        raise HTTPException(status_code=500, detail=f"Push to git failed: {exc}")


# ═════════════════════════════════════════════════════════════════════════════
# v2-only: Graph introspection
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/v2/graphs", tags=["v2"])
async def list_graphs():
    return {
        "graphs": [
            {
                "name": "automation-pipeline",
                "description": "Generate → Execute → Evaluate → Repair loop for Playwright automations",
                "nodes": ["generate", "execute", "repair", "output"],
                "edges": [
                    {"from": "START", "to": "generate"},
                    {"from": "generate", "to": "execute"},
                    {"from": "execute", "to": "repair", "condition": "failed and retries left"},
                    {"from": "execute", "to": "output", "condition": "success or no retries left"},
                    {"from": "repair", "to": "execute"},
                    {"from": "output", "to": "END"},
                ],
            }
        ]
    }


# ═════════════════════════════════════════════════════════════════════════════
# Health
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["health"])
async def health():
    llm = await check_azure_llm(AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY)
    mcp = await check_playwright_mcp(PLAYWRIGHT_MCP_URL)
    pinchtab = await check_http_service(PINCHTAB_URL + "/health", "pinchtab")
    deps = {"azure_llm": llm, "playwright_mcp": mcp, "pinchtab": pinchtab}
    status = aggregate_health_status(deps)
    return {
        "service": "generator-v2",
        "version": "2.0.0",
        "engine": "langchain+langgraph",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": deps,
    }
