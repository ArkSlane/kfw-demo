"""
Orchestrator Service — the central agentic brain of the platform.

Coordinates multi-service workflows, maintains persistent memory of what
works and what doesn't, tracks quality feedback, and provides improvement
suggestions.

Endpoints:
  # Workflows
  POST /workflows/release-coverage     — analyse + fill coverage gaps for a release
  POST /workflows/test-plan            — auto-generate test cases for a requirement
  POST /workflows/batch-execute        — run automations for multiple test cases

  # Agent Memory
  POST /memory/record-outcome          — record a generation/execution outcome
  POST /memory/record-selector         — record a selector success/failure
  POST /memory/record-repair           — record a repair insight
  GET  /memory/prompt-block            — get learnings formatted for LLM prompt injection
  GET  /memory/stats                   — overall quality stats

  # Feedback & Insights
  GET  /feedback/quality-trend         — daily quality trend
  GET  /feedback/failure-breakdown     — failures grouped by error type
  GET  /feedback/page-difficulty       — pages ranked by failure rate
  GET  /feedback/suggestions           — AI-generated improvement suggestions

  # Reports
  GET  /reports                        — list past workflow reports

  # Health
  GET  /health                         — service health
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from shared.db import get_db, close_client
from shared.errors import setup_all_error_handlers
from shared.health import check_mongodb, aggregate_health_status
from shared.settings import MONGO_URL, DB_NAME, CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT_JSON, validate_settings
from shared.logging_config import setup_logging, get_logger
from shared.auth import setup_auth
from shared.rate_limit import setup_rate_limiting
from shared.indexes import ensure_indexes
import agent_memory
import feedback
import workflows

logger = get_logger(__name__)

# ── Service URLs ─────────────────────────────────────────────────────────────
REQUIREMENTS_URL = os.getenv("REQUIREMENTS_SERVICE_URL", "http://requirements:8000")
TESTCASES_URL = os.getenv("TESTCASES_SERVICE_URL", "http://testcases:8000")
GENERATOR_URL = os.getenv("GENERATOR_SERVICE_URL", "http://generator:8000")
RELEASES_URL = os.getenv("RELEASES_SERVICE_URL", "http://releases:8000")
AUTOMATIONS_URL = os.getenv("AUTOMATIONS_SERVICE_URL", "http://automations:8000")
EXECUTIONS_URL = os.getenv("EXECUTIONS_SERVICE_URL", "http://executions:8000")


def _fwd_headers(request: Request) -> dict:
    """Extract Authorization header for service-to-service forwarding."""
    auth = request.headers.get("authorization", "")
    return {"Authorization": auth} if auth else {}


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_settings()
    setup_logging("orchestrator", level=LOG_LEVEL, json_output=LOG_FORMAT_JSON)
    db = get_db()
    await ensure_indexes(db, ["agent_memory"])
    logger.info("Orchestrator ready — agentic brain online")
    yield
    await close_client()


app = FastAPI(
    title="Orchestrator Service",
    description="Central agentic brain — coordinates workflows, learns from outcomes, and improves over time.",
    version="1.0.0",
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
# Request / Response models
# ═════════════════════════════════════════════════════════════════════════════

class ReleaseCoverageRequest(BaseModel):
    release_id: str = Field(..., max_length=50)
    auto_generate: bool = Field(False, description="Auto-generate test cases for uncovered requirements")
    auto_execute: bool = Field(False, description="Auto-generate and execute automations for new test cases")


class TestPlanRequest(BaseModel):
    requirement_id: str = Field(..., max_length=50)
    amount: int = Field(3, ge=1, le=10, description="Number of test cases to generate")


class BatchExecuteRequest(BaseModel):
    test_case_ids: list[str] = Field(..., min_length=1, max_length=100)


class RecordOutcomeRequest(BaseModel):
    test_case_id: str = Field(..., max_length=50)
    requirement_id: Optional[str] = Field(None, max_length=50)
    model: str = Field(..., max_length=100)
    generation_mode: str = Field(..., max_length=50)
    first_try_success: bool
    repair_attempts: int = Field(0, ge=0)
    final_success: bool
    error_type: Optional[str] = Field(None, max_length=200)
    duration_ms: Optional[int] = Field(None, ge=0)
    page: Optional[str] = Field(None, max_length=200)


class RecordSelectorRequest(BaseModel):
    page: str = Field(..., max_length=200)
    selector: str = Field(..., max_length=500)
    success: bool
    error_snippet: Optional[str] = Field(None, max_length=500)
    learned_fix: Optional[str] = Field(None, max_length=500)


class RecordRepairRequest(BaseModel):
    error_pattern: str = Field(..., max_length=500)
    fix_description: str = Field(..., max_length=500)
    page: Optional[str] = Field(None, max_length=200)
    success: bool = True


# ═════════════════════════════════════════════════════════════════════════════
# Workflow endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/workflows/release-coverage", tags=["workflows"])
async def run_release_coverage(payload: ReleaseCoverageRequest, request: Request):
    """Analyse a release for test coverage gaps and optionally auto-generate tests."""
    db = get_db()
    report = await workflows.workflow_release_coverage(
        db,
        payload.release_id,
        requirements_url=REQUIREMENTS_URL,
        testcases_url=TESTCASES_URL,
        generator_url=GENERATOR_URL,
        automations_url=AUTOMATIONS_URL,
        auth_headers=_fwd_headers(request),
        auto_generate=payload.auto_generate,
        auto_execute=payload.auto_execute,
    )
    return report


@app.post("/workflows/test-plan", tags=["workflows"])
async def run_test_plan(payload: TestPlanRequest, request: Request):
    """Auto-generate test cases for a requirement if none exist."""
    db = get_db()
    report = await workflows.workflow_autonomous_test_plan(
        db,
        payload.requirement_id,
        requirements_url=REQUIREMENTS_URL,
        testcases_url=TESTCASES_URL,
        generator_url=GENERATOR_URL,
        auth_headers=_fwd_headers(request),
        amount=payload.amount,
    )
    return report


@app.post("/workflows/batch-execute", tags=["workflows"])
async def run_batch_execute(payload: BatchExecuteRequest, request: Request):
    """Execute automations for a batch of test cases."""
    db = get_db()
    report = await workflows.workflow_batch_execute(
        db,
        payload.test_case_ids,
        generator_url=GENERATOR_URL,
        auth_headers=_fwd_headers(request),
    )
    return report


# ═════════════════════════════════════════════════════════════════════════════
# Agent Memory endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/memory/record-outcome", tags=["memory"], status_code=201)
async def record_outcome(payload: RecordOutcomeRequest):
    """Record a generation/execution outcome for learning."""
    db = get_db()
    await agent_memory.record_generation_outcome(
        db,
        test_case_id=payload.test_case_id,
        requirement_id=payload.requirement_id,
        model=payload.model,
        generation_mode=payload.generation_mode,
        first_try_success=payload.first_try_success,
        repair_attempts=payload.repair_attempts,
        final_success=payload.final_success,
        error_type=payload.error_type,
        duration_ms=payload.duration_ms,
        page=payload.page,
    )
    return {"status": "recorded"}


@app.post("/memory/record-selector", tags=["memory"], status_code=201)
async def record_selector(payload: RecordSelectorRequest):
    """Record a selector success/failure for a page."""
    db = get_db()
    await agent_memory.record_selector_outcome(
        db,
        page=payload.page,
        selector=payload.selector,
        success=payload.success,
        error_snippet=payload.error_snippet,
        learned_fix=payload.learned_fix,
    )
    return {"status": "recorded"}


@app.post("/memory/record-repair", tags=["memory"], status_code=201)
async def record_repair(payload: RecordRepairRequest):
    """Record a repair pattern that worked or failed."""
    db = get_db()
    await agent_memory.record_repair_insight(
        db,
        error_pattern=payload.error_pattern,
        fix_description=payload.fix_description,
        page=payload.page,
        success=payload.success,
    )
    return {"status": "recorded"}


@app.get("/memory/prompt-block", tags=["memory"])
async def get_prompt_block(page: Optional[str] = Query(None, max_length=200)):
    """Get a formatted prompt block with learnings for injection into LLM prompts."""
    db = get_db()
    block = await agent_memory.build_memory_prompt_block(db, page=page)
    return {"prompt_block": block}


@app.get("/memory/stats", tags=["memory"])
async def get_stats(days: int = Query(7, ge=1, le=365)):
    """Get overall generation quality stats."""
    db = get_db()
    stats = await agent_memory.get_generation_stats(db, days=days)
    return stats


@app.get("/memory/selectors", tags=["memory"])
async def get_selectors(page: Optional[str] = Query(None, max_length=200), limit: int = Query(50, ge=1, le=200)):
    """Get selector insights, optionally filtered by page."""
    db = get_db()
    selectors = await agent_memory.get_selector_insights(db, page=page, limit=limit)
    return selectors


@app.get("/memory/repairs", tags=["memory"])
async def get_repairs(limit: int = Query(20, ge=1, le=100)):
    """Get repair insights sorted by success count."""
    db = get_db()
    repairs = await agent_memory.get_repair_insights(db, limit=limit)
    return repairs


# ═════════════════════════════════════════════════════════════════════════════
# Feedback endpoints
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/feedback/quality-trend", tags=["feedback"])
async def quality_trend(days: int = Query(30, ge=1, le=365)):
    """Daily quality trend (success rate over time)."""
    db = get_db()
    return await feedback.get_quality_trend(db, days=days)


@app.get("/feedback/failure-breakdown", tags=["feedback"])
async def failure_breakdown(days: int = Query(30, ge=1, le=365)):
    """Failures grouped by error type."""
    db = get_db()
    return await feedback.get_failure_breakdown(db, days=days)


@app.get("/feedback/page-difficulty", tags=["feedback"])
async def page_difficulty(days: int = Query(30, ge=1, le=365)):
    """Pages ranked by failure rate."""
    db = get_db()
    return await feedback.get_page_difficulty(db, days=days)


@app.get("/feedback/suggestions", tags=["feedback"])
async def improvement_suggestions(days: int = Query(14, ge=1, le=365)):
    """AI-generated improvement suggestions based on accumulated data."""
    db = get_db()
    suggestions = await feedback.suggest_improvements(db, days=days)
    return {"suggestions": suggestions}


# ═════════════════════════════════════════════════════════════════════════════
# Reports
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/reports", tags=["reports"])
async def list_reports(
    workflow: Optional[str] = Query(None, max_length=50),
    limit: int = Query(20, ge=1, le=100),
):
    """List past workflow reports."""
    db = get_db()
    query: dict = {"type": "workflow_report"}
    if workflow:
        query["workflow"] = workflow
    cursor = db["orchestrator_reports"].find(query).sort("started_at", -1).limit(limit)
    reports = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        reports.append(doc)
    return reports


# ═════════════════════════════════════════════════════════════════════════════
# Health
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["health"])
async def health_check():
    """Service health check."""
    mongo = await check_mongodb(MONGO_URL, DB_NAME)
    deps = {"mongodb": mongo}
    status = aggregate_health_status(deps)
    return {
        "service": "orchestrator",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": deps,
    }
