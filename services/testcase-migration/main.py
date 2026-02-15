from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from shared.errors import setup_all_error_handlers


def _fwd_headers(request: Request) -> dict:
    """Extract Authorization header for service-to-service forwarding."""
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}
from shared.health import aggregate_health_status, check_http_service, check_ollama
from shared.settings import CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting

logger = get_logger(__name__)


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
# Deterministic sampling params
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_TOP_P = float(os.getenv("OLLAMA_TOP_P", "1"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "2048"))

TESTCASES_URL = os.getenv("TESTCASES_SERVICE_URL", "http://testcases:8000")
GENERATOR_URL = os.getenv("GENERATOR_SERVICE_URL", "http://generator:8000")
AUTOMATIONS_URL = os.getenv("AUTOMATIONS_SERVICE_URL", "http://automations:8000")

UNLINKED_REQUIREMENT_ID = os.getenv("MIGRATION_REQUIREMENT_ID", "unlinked")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_markdown_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
    t = re.sub(r"```\s*$", "", t)
    return t.strip()


def _extract_first_json_object(text: str) -> str | None:
    # Best-effort: find first balanced {...} object
    t = (text or "").strip()
    if not t:
        return None
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        ch = t[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return t[start : i + 1]
    return None


class TestStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str
    expected_result: str | None = None


class TestcaseDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(default="Migrated Testcase")
    description: str | None = None
    preconditions: str | None = None
    steps: list[TestStep] = Field(default_factory=list)


class CodeToStepMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")
    step_number: int = Field(..., ge=1)
    code_snippet: str
    notes: str | None = None


class AnalyzeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str | None = None


class AnalyzeResponse(BaseModel):
    testcase: TestcaseDraft
    mapping: list[CodeToStepMapping]
    model: str
    generated_at: str


class GenerateAutomationDraftRequest(BaseModel):
    code: str | None = None
    testcase: TestcaseDraft
    mapping: list[CodeToStepMapping] = Field(default_factory=list)


class AutomationDraftOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # passthrough shape from generator
    title: str
    framework: str | None = None
    script_outline: str
    notes: str | None = None
    actions_taken: str | None = None
    exec_success: bool | None = None
    exec_error: str | None = None
    transcript: Any | None = None
    video_filename: str | None = None
    video_path: str | None = None


class GenerateAutomationDraftResponse(BaseModel):
    testcase_id: str
    testcase: dict
    draft: AutomationDraftOut


class SaveMigrationRequest(BaseModel):
    testcase_id: str
    testcase: TestcaseDraft
    mapping: list[CodeToStepMapping] = Field(default_factory=list)
    script: str
    framework: str | None = None
    notes: str | None = None


class SaveMigrationResponse(BaseModel):
    testcase_id: str
    automation_id: str


def _steps_to_gherkin(title: str, steps: list[TestStep]) -> str:
    clean_title = (title or "Migrated Testcase").strip() or "Migrated Testcase"
    lines = [f"Feature: Migration", "", f"Scenario: {clean_title}"]
    if not steps:
        lines.append("  Given the system is ready")
        return "\n".join(lines)

    # First step as Given, rest as And
    first = steps[0]
    lines.append(f"  Given {first.action}")
    if first.expected_result:
        lines.append(f"  And expected: {first.expected_result}")

    for s in steps[1:]:
        lines.append(f"  And {s.action}")
        if s.expected_result:
            lines.append(f"  And expected: {s.expected_result}")

    return "\n".join(lines)


def _heuristic_analyze(code: str) -> tuple[TestcaseDraft, list[CodeToStepMapping]]:
    # Basic fallback so the UI can work even if the LLM is down.
    lines = (code or "").splitlines()
    steps: list[TestStep] = []
    mapping: list[CodeToStepMapping] = []

    def add_step(action: str, expected: str | None, snippet: str):
        steps.append(TestStep(action=action, expected_result=expected))
        mapping.append(CodeToStepMapping(step_number=len(steps), code_snippet=snippet))

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("'"):
            continue

        if "SystemUtil.Run" in line:
            add_step("Open the application in a browser", "Application opens", raw)
        elif ".Sync" in line:
            add_step("Wait for the page to load", "Page is loaded", raw)
        elif ".Set" in line:
            add_step("Enter the required text into the input field", None, raw)
        elif ".Type" in line:
            add_step("Submit the input (press Enter)", None, raw)
        elif ".Exist" in line:
            add_step("Verify that the expected element exists", "Element is present", raw)
        elif ".Close" in line:
            add_step("Close the browser", "Browser closes", raw)

    title = "Migrated test from automation code"
    desc = "Testcase draft generated from pasted automation code. Review and adjust before saving."
    return TestcaseDraft(title=title, description=desc, steps=steps), mapping


async def _ollama_json(prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": float(OLLAMA_TEMPERATURE),
                "top_p": float(OLLAMA_TOP_P),
                "max_tokens": int(OLLAMA_MAX_TOKENS),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or data.get("output") or "").strip()
        if not text:
            raise ValueError("empty LLM response")
        text = _strip_markdown_code_fences(text)
        json_text = _extract_first_json_object(text) or text
        return json.loads(json_text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("testcase-migration", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    logger.info("Testcase Migration service ready")
    yield
    logger.info("Testcase Migration service stopped")


app = FastAPI(
    lifespan=lifespan,
    title="Testcase Migration Service",
    version="1.0.0",
    description=(
        "Service that converts pasted legacy test automation code into a structured testcase draft, "
        "then helps generate and review an AI automation draft before saving."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

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


@app.get("/health")
async def health():
    deps = {
        "ollama": await check_ollama(OLLAMA_URL),
        "testcases_service": await check_http_service("testcases", TESTCASES_URL),
        "generator_service": await check_http_service("generator", GENERATOR_URL),
        "automations_service": await check_http_service("automations", AUTOMATIONS_URL),
    }
    return {
        "status": aggregate_health_status(deps),
        "service": "testcase-migration",
        "timestamp": now_iso(),
        "dependencies": deps,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest):
    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    schema_hint = (
        '{"testcase":{"title":"...","description":"...","preconditions":"...",'
        '"steps":[{"action":"...","expected_result":"..."}]},'
        '"mapping":[{"step_number":1,"code_snippet":"...","notes":"..."}]}'
    )

    prompt = (
        "You are a QA engineer migrating legacy automation scripts into a manual test case. "
        "Return JSON ONLY (no markdown, no code fences, no explanation). "
        f"Schema: {schema_hint}. "
        "Rules: step_number starts at 1 and corresponds to testcase.steps index. "
        "Use short, clear actions; expected_result can be null when not applicable. "
        "For mapping.code_snippet, include the relevant code line(s) that caused that step. "
        "If the script contains verification (Exist/ReportEvent), express it as an assertion step. "
        "\n\nAutomation code:\n" + code
    )

    try:
        parsed = await _ollama_json(prompt)
        testcase = TestcaseDraft.model_validate(parsed.get("testcase") or {})
        mapping = [CodeToStepMapping.model_validate(x) for x in (parsed.get("mapping") or [])]
        if not testcase.steps:
            # Ensure there is always something usable
            fallback_tc, fallback_map = _heuristic_analyze(code)
            testcase = fallback_tc
            mapping = fallback_map
        return AnalyzeResponse(testcase=testcase, mapping=mapping, model=OLLAMA_MODEL, generated_at=now_iso())
    except Exception:
        testcase, mapping = _heuristic_analyze(code)
        return AnalyzeResponse(testcase=testcase, mapping=mapping, model="heuristic", generated_at=now_iso())


@app.post("/generate-automation-draft", response_model=GenerateAutomationDraftResponse)
async def generate_automation_draft(payload: GenerateAutomationDraftRequest, request: Request):
    # 1) Create a draft testcase in the testcases service (needed because generator expects an id)
    tc = payload.testcase
    steps = tc.steps or []
    gherkin = _steps_to_gherkin(tc.title, steps)

    tc_create = {
        "requirement_id": UNLINKED_REQUIREMENT_ID,
        "title": tc.title,
        "gherkin": gherkin,
        "status": "draft",
        "version": 1,
        "metadata": {
            "source": "testcase-migration",
            "description": tc.description or "",
            "preconditions": tc.preconditions or "",
            "steps": [s.model_dump() for s in steps],
            "mapping": [m.model_dump() for m in (payload.mapping or [])],
            "raw_code": (payload.code or "")[:200000],
            "generated_at": now_iso(),
        },
    }

    async with httpx.AsyncClient(timeout=300, headers=_fwd_headers(request)) as client:
        created = await client.post(f"{TESTCASES_URL}/testcases", json=tc_create)
        if created.status_code not in (200, 201):
            raise HTTPException(status_code=created.status_code, detail=created.text)
        testcase_doc = created.json()
        testcase_id = testcase_doc.get("id")
        if not testcase_id:
            raise HTTPException(status_code=500, detail="testcases service returned no id")

        # 2) Use the existing generator flow that produces a reviewable automation draft (not persisted)
        draft_resp = await client.post(
            f"{GENERATOR_URL}/generate-automation-draft-from-execution",
            json={"test_case_id": testcase_id},
        )
        if draft_resp.status_code != 200:
            raise HTTPException(status_code=draft_resp.status_code, detail=draft_resp.text)

        draft = AutomationDraftOut.model_validate(draft_resp.json())

    return GenerateAutomationDraftResponse(testcase_id=testcase_id, testcase=testcase_doc, draft=draft)


@app.post("/save", response_model=SaveMigrationResponse)
async def save(payload: SaveMigrationRequest, request: Request):
    testcase_id = (payload.testcase_id or "").strip()
    if not testcase_id:
        raise HTTPException(status_code=400, detail="testcase_id is required")

    tc = payload.testcase
    steps = tc.steps or []
    gherkin = _steps_to_gherkin(tc.title, steps)

    # 1) Finalize testcase (keep same id, flip to ready)
    tc_patch = {
        "title": tc.title,
        "gherkin": gherkin,
        "status": "ready",
        "metadata": {
            "source": "testcase-migration",
            "description": tc.description or "",
            "preconditions": tc.preconditions or "",
            "steps": [s.model_dump() for s in steps],
            "mapping": [m.model_dump() for m in (payload.mapping or [])],
            "finalized_at": now_iso(),
        },
    }

    # 2) Create automation (persist)
    automation_create = {
        "test_case_id": testcase_id,
        "title": tc.title,
        "framework": payload.framework or "playwright",
        "script": payload.script,
        "status": "not_started",
        "metadata": {
            "source": "testcase-migration",
            "notes": payload.notes or "",
            "finalized_at": now_iso(),
        },
    }

    async with httpx.AsyncClient(timeout=60, headers=_fwd_headers(request)) as client:
        updated = await client.put(f"{TESTCASES_URL}/testcases/{testcase_id}", json=tc_patch)
        if updated.status_code != 200:
            raise HTTPException(status_code=updated.status_code, detail=updated.text)

        created_auto = await client.post(f"{AUTOMATIONS_URL}/automations", json=automation_create)
        if created_auto.status_code not in (200, 201):
            raise HTTPException(status_code=created_auto.status_code, detail=created_auto.text)
        auto_doc = created_auto.json()
        automation_id = auto_doc.get("id")
        if not automation_id:
            raise HTTPException(status_code=500, detail="automations service returned no id")

    return SaveMigrationResponse(testcase_id=testcase_id, automation_id=automation_id)
