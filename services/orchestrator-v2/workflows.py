"""
LangGraph-based autonomous workflows (v2).

Each workflow is defined as a LangGraph StateGraph with typed state,
explicit nodes, and conditional edges.  The graph structure makes the
control flow visible and debuggable vs. the v1 imperative approach.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Annotated, Optional
from operator import add

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig

from agent_memory import record_generation_outcome

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═════════════════════════════════════════════════════════════════════════════
# Workflow 1 — Release Coverage Analysis
# ═════════════════════════════════════════════════════════════════════════════

class ReleaseCoverageState(BaseModel):
    """Typed state flowing through the release-coverage graph."""
    # Inputs
    release_id: str
    requirements_url: str
    testcases_url: str
    generator_url: str
    automations_url: str
    auth_headers: dict = Field(default_factory=dict)
    auto_generate: bool = False
    auto_execute: bool = False

    # Working state
    requirements: list[dict] = Field(default_factory=list)
    gaps: list[dict] = Field(default_factory=list)
    generated_testcases: list[str] = Field(default_factory=list)
    generated_automations: list[str] = Field(default_factory=list)
    errors: Annotated[list[str], add] = Field(default_factory=list)
    requirements_covered: int = 0
    requirements_uncovered: int = 0

    # Output
    started_at: str = ""
    completed_at: str = ""
    coverage_pct: float = 0.0

    # DB reference (excluded from serialisation)
    db: Optional[object] = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


async def _rc_fetch_requirements(state: ReleaseCoverageState) -> dict:
    """Node: fetch all requirements for the release."""
    try:
        async with httpx.AsyncClient(timeout=60, headers=state.auth_headers) as client:
            resp = await client.get(
                f"{state.requirements_url}/requirements",
                params={"release_id": state.release_id},
            )
            resp.raise_for_status()
            data = resp.json()
            reqs = data if isinstance(data, list) else data.get("items", data.get("requirements", []))
            return {"requirements": reqs, "started_at": _now_iso()}
    except Exception as e:
        return {"errors": [f"Failed to fetch requirements: {e}"], "started_at": _now_iso()}


async def _rc_check_coverage(state: ReleaseCoverageState) -> dict:
    """Node: for each requirement check if linked test cases exist."""
    covered = 0
    uncovered = 0
    gaps: list[dict] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=60, headers=state.auth_headers) as client:
        for req in state.requirements:
            req_id = req.get("id") or str(req.get("_id", ""))
            req_title = req.get("title", "Untitled")
            try:
                tc_resp = await client.get(
                    f"{state.testcases_url}/testcases",
                    params={"requirement_id": req_id},
                )
                tc_resp.raise_for_status()
                tc_data = tc_resp.json()
                testcases = tc_data if isinstance(tc_data, list) else tc_data.get("items", tc_data.get("testcases", []))
            except Exception as e:
                errors.append(f"Coverage check failed for req {req_id}: {e}")
                testcases = []

            if testcases:
                covered += 1
            else:
                uncovered += 1
                gaps.append({"requirement_id": req_id, "title": req_title})

    return {
        "requirements_covered": covered,
        "requirements_uncovered": uncovered,
        "gaps": gaps,
        "errors": errors,
    }


def _rc_should_generate(state: ReleaseCoverageState) -> str:
    """Conditional edge: decide whether to generate tests for gaps."""
    if state.auto_generate and state.gaps:
        return "generate"
    return "finalise"


async def _rc_generate_tests(state: ReleaseCoverageState) -> dict:
    """Node: auto-generate test cases for uncovered requirements."""
    generated: list[str] = []
    automations: list[str] = []
    errors: list[str] = []
    gaps = list(state.gaps)  # work on a copy

    async with httpx.AsyncClient(timeout=300, headers=state.auth_headers) as client:
        for gap in gaps:
            req_id = gap["requirement_id"]
            try:
                gen_resp = await client.post(
                    f"{state.generator_url}/generate-structured-testcase",
                    json={"requirement_id": req_id},
                    timeout=180,
                )
                gen_resp.raise_for_status()
                gen_data = gen_resp.json()
                tc_id = gen_data.get("testcase_id") or gen_data.get("id")
                gap["generated_testcase_id"] = tc_id
                generated.append(tc_id)
                logger.info("Generated testcase %s for requirement %s", tc_id, req_id)

                if state.auto_execute and tc_id:
                    t0 = time.monotonic()
                    try:
                        auto_resp = await client.post(
                            f"{state.generator_url}/generate-automation-from-execution",
                            json={"test_case_id": tc_id},
                            timeout=300,
                        )
                        auto_resp.raise_for_status()
                        auto_data = auto_resp.json()
                        duration_ms = int((time.monotonic() - t0) * 1000)
                        gap["automation_id"] = auto_data.get("automation_id") or auto_data.get("id")
                        gap["automation_status"] = auto_data.get("status")
                        automations.append(gap["automation_id"])

                        if state.db:
                            await record_generation_outcome(
                                state.db,
                                test_case_id=tc_id,
                                requirement_id=req_id,
                                model=auto_data.get("model", "unknown"),
                                generation_mode=auto_data.get("generation_mode", "orchestrated"),
                                first_try_success=auto_data.get("repair_attempts", 0) == 0 and auto_data.get("status") == "not_started",
                                repair_attempts=auto_data.get("repair_attempts", 0),
                                final_success=auto_data.get("status") == "not_started",
                                error_type=auto_data.get("error_type"),
                                duration_ms=duration_ms,
                            )
                    except Exception as e:
                        errors.append(f"Automation failed for tc {tc_id}: {e}")
            except Exception as e:
                errors.append(f"Generation failed for req {req_id}: {e}")

    return {
        "generated_testcases": generated,
        "generated_automations": automations,
        "gaps": gaps,
        "errors": errors,
    }


async def _rc_finalise(state: ReleaseCoverageState) -> dict:
    """Node: compute final metrics and persist report."""
    total = len(state.requirements) or 1
    coverage_pct = round(state.requirements_covered / total * 100, 1)

    report = {
        "release_id": state.release_id,
        "started_at": state.started_at,
        "completed_at": _now_iso(),
        "requirements_total": len(state.requirements),
        "requirements_covered": state.requirements_covered,
        "requirements_uncovered": state.requirements_uncovered,
        "coverage_pct": coverage_pct,
        "gaps": state.gaps,
        "generated_testcases": state.generated_testcases,
        "generated_automations": state.generated_automations,
        "errors": state.errors,
    }

    if state.db:
        report_doc = {**report, "type": "workflow_report", "workflow": "release_coverage"}
        await state.db["orchestrator_reports"].insert_one(report_doc)

    return {"coverage_pct": coverage_pct, "completed_at": report["completed_at"]}


def build_release_coverage_graph() -> StateGraph:
    """Build and compile the release-coverage LangGraph."""
    graph = StateGraph(ReleaseCoverageState)

    graph.add_node("fetch_requirements", _rc_fetch_requirements)
    graph.add_node("check_coverage", _rc_check_coverage)
    graph.add_node("generate_tests", _rc_generate_tests)
    graph.add_node("finalise", _rc_finalise)

    graph.add_edge(START, "fetch_requirements")
    graph.add_edge("fetch_requirements", "check_coverage")
    graph.add_conditional_edges("check_coverage", _rc_should_generate, {
        "generate": "generate_tests",
        "finalise": "finalise",
    })
    graph.add_edge("generate_tests", "finalise")
    graph.add_edge("finalise", END)

    return graph.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Workflow 2 — Autonomous Test Plan
# ═════════════════════════════════════════════════════════════════════════════

class TestPlanState(BaseModel):
    """Typed state for the test-plan graph."""
    requirement_id: str
    requirements_url: str
    testcases_url: str
    generator_url: str
    auth_headers: dict = Field(default_factory=dict)
    amount: int = 3

    requirement_title: str = ""
    existing_testcases: int = 0
    generated_testcases: list[str] = Field(default_factory=list)
    errors: Annotated[list[str], add] = Field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    db: Optional[object] = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


async def _tp_fetch_requirement(state: TestPlanState) -> dict:
    try:
        async with httpx.AsyncClient(timeout=60, headers=state.auth_headers) as client:
            resp = await client.get(f"{state.requirements_url}/requirements/{state.requirement_id}")
            resp.raise_for_status()
            requirement = resp.json()
            return {
                "requirement_title": requirement.get("title", ""),
                "started_at": _now_iso(),
            }
    except Exception as e:
        return {"errors": [f"Failed to fetch requirement: {e}"], "started_at": _now_iso()}


async def _tp_check_existing(state: TestPlanState) -> dict:
    try:
        async with httpx.AsyncClient(timeout=60, headers=state.auth_headers) as client:
            tc_resp = await client.get(
                f"{state.testcases_url}/testcases",
                params={"requirement_id": state.requirement_id},
            )
            tc_resp.raise_for_status()
            tc_data = tc_resp.json()
            existing = tc_data if isinstance(tc_data, list) else tc_data.get("items", tc_data.get("testcases", []))
            return {"existing_testcases": len(existing)}
    except Exception:
        return {"existing_testcases": 0}


def _tp_should_generate(state: TestPlanState) -> str:
    if state.existing_testcases == 0:
        return "generate"
    return "finalise"


async def _tp_generate(state: TestPlanState) -> dict:
    try:
        async with httpx.AsyncClient(timeout=180, headers=state.auth_headers) as client:
            gen_resp = await client.post(
                f"{state.generator_url}/generate",
                json={"requirement_id": state.requirement_id, "amount": state.amount},
                timeout=180,
            )
            gen_resp.raise_for_status()
            gen_data = gen_resp.json()
            generated = gen_data.get("generated", [])
            logger.info("Auto-generated %d testcases for requirement %s", len(generated), state.requirement_id)
            return {"generated_testcases": [tc.get("id", "") for tc in generated]}
    except Exception as e:
        return {"errors": [f"Generation failed: {e}"]}


async def _tp_finalise(state: TestPlanState) -> dict:
    report = {
        "requirement_id": state.requirement_id,
        "requirement_title": state.requirement_title,
        "started_at": state.started_at,
        "completed_at": _now_iso(),
        "existing_testcases": state.existing_testcases,
        "generated_testcases": state.generated_testcases,
        "errors": state.errors,
    }
    if state.db:
        report_doc = {**report, "type": "workflow_report", "workflow": "autonomous_test_plan"}
        await state.db["orchestrator_reports"].insert_one(report_doc)
    return {"completed_at": report["completed_at"]}


def build_test_plan_graph() -> StateGraph:
    graph = StateGraph(TestPlanState)

    graph.add_node("fetch_requirement", _tp_fetch_requirement)
    graph.add_node("check_existing", _tp_check_existing)
    graph.add_node("generate", _tp_generate)
    graph.add_node("finalise", _tp_finalise)

    graph.add_edge(START, "fetch_requirement")
    graph.add_edge("fetch_requirement", "check_existing")
    graph.add_conditional_edges("check_existing", _tp_should_generate, {
        "generate": "generate",
        "finalise": "finalise",
    })
    graph.add_edge("generate", "finalise")
    graph.add_edge("finalise", END)

    return graph.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Workflow 3 — Batch Execute
# ═════════════════════════════════════════════════════════════════════════════

class BatchExecuteState(BaseModel):
    """Typed state for batch-execute graph."""
    test_case_ids: list[str]
    generator_url: str
    auth_headers: dict = Field(default_factory=dict)

    results: list[dict] = Field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    errors: Annotated[list[str], add] = Field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    current_index: int = 0

    db: Optional[object] = Field(default=None, exclude=True)

    model_config = {"arbitrary_types_allowed": True}


async def _be_init(state: BatchExecuteState) -> dict:
    return {"started_at": _now_iso(), "current_index": 0}


async def _be_execute_one(state: BatchExecuteState) -> dict:
    """Execute the test case at current_index."""
    idx = state.current_index
    tc_id = state.test_case_ids[idx]
    result: dict = {"test_case_id": tc_id}
    succeeded = 0
    failed = 0
    errors: list[str] = []

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=300, headers=state.auth_headers) as client:
            resp = await client.post(
                f"{state.generator_url}/generate-automation-from-execution",
                json={"test_case_id": tc_id},
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
            duration_ms = int((time.monotonic() - t0) * 1000)
            success = data.get("status") == "not_started"
            result["status"] = data.get("status", "unknown")
            result["automation_id"] = data.get("automation_id") or data.get("id")
            result["duration_ms"] = duration_ms

            if success:
                succeeded = 1
            else:
                failed = 1

            if state.db:
                await record_generation_outcome(
                    state.db,
                    test_case_id=tc_id,
                    model=data.get("model", "unknown"),
                    generation_mode="batch_execute",
                    first_try_success=data.get("repair_attempts", 0) == 0 and success,
                    repair_attempts=data.get("repair_attempts", 0),
                    final_success=success,
                    error_type=data.get("error_type"),
                    duration_ms=duration_ms,
                )
    except Exception as e:
        failed = 1
        result["error"] = str(e)
        errors.append(f"Execution failed for tc {tc_id}: {e}")

    return {
        "results": state.results + [result],
        "succeeded": state.succeeded + succeeded,
        "failed": state.failed + failed,
        "errors": errors,
        "current_index": idx + 1,
    }


def _be_has_more(state: BatchExecuteState) -> str:
    if state.current_index < len(state.test_case_ids):
        return "execute_one"
    return "finalise"


async def _be_finalise(state: BatchExecuteState) -> dict:
    report = {
        "started_at": state.started_at,
        "completed_at": _now_iso(),
        "total": len(state.test_case_ids),
        "succeeded": state.succeeded,
        "failed": state.failed,
        "results": state.results,
        "errors": state.errors,
    }
    if state.db:
        report_doc = {**report, "type": "workflow_report", "workflow": "batch_execute"}
        await state.db["orchestrator_reports"].insert_one(report_doc)
    return {"completed_at": report["completed_at"]}


def build_batch_execute_graph() -> StateGraph:
    graph = StateGraph(BatchExecuteState)

    graph.add_node("init", _be_init)
    graph.add_node("execute_one", _be_execute_one)
    graph.add_node("finalise", _be_finalise)

    graph.add_edge(START, "init")
    graph.add_conditional_edges("init", _be_has_more, {
        "execute_one": "execute_one",
        "finalise": "finalise",
    })
    graph.add_conditional_edges("execute_one", _be_has_more, {
        "execute_one": "execute_one",
        "finalise": "finalise",
    })
    graph.add_edge("finalise", END)

    return graph.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Public API — called from main.py
# ═════════════════════════════════════════════════════════════════════════════

_release_coverage_graph = None
_test_plan_graph = None
_batch_execute_graph = None


def _get_release_coverage_graph():
    global _release_coverage_graph
    if _release_coverage_graph is None:
        _release_coverage_graph = build_release_coverage_graph()
    return _release_coverage_graph


def _get_test_plan_graph():
    global _test_plan_graph
    if _test_plan_graph is None:
        _test_plan_graph = build_test_plan_graph()
    return _test_plan_graph


def _get_batch_execute_graph():
    global _batch_execute_graph
    if _batch_execute_graph is None:
        _batch_execute_graph = build_batch_execute_graph()
    return _batch_execute_graph


async def workflow_release_coverage(
    db: AsyncIOMotorDatabase,
    release_id: str,
    *,
    requirements_url: str,
    testcases_url: str,
    generator_url: str,
    automations_url: str,
    auth_headers: dict,
    auto_generate: bool = False,
    auto_execute: bool = False,
) -> dict:
    """Run the release-coverage graph and return the report."""
    graph = _get_release_coverage_graph()
    initial_state = ReleaseCoverageState(
        release_id=release_id,
        requirements_url=requirements_url,
        testcases_url=testcases_url,
        generator_url=generator_url,
        automations_url=automations_url,
        auth_headers=auth_headers,
        auto_generate=auto_generate,
        auto_execute=auto_execute,
        db=db,
    )
    final_state = await graph.ainvoke(initial_state)
    # Build report dict from final state
    s = final_state if isinstance(final_state, dict) else final_state.__dict__
    return {
        "release_id": s.get("release_id", release_id),
        "started_at": s.get("started_at", ""),
        "completed_at": s.get("completed_at", ""),
        "requirements_total": len(s.get("requirements", [])),
        "requirements_covered": s.get("requirements_covered", 0),
        "requirements_uncovered": s.get("requirements_uncovered", 0),
        "coverage_pct": s.get("coverage_pct", 0.0),
        "gaps": s.get("gaps", []),
        "generated_testcases": s.get("generated_testcases", []),
        "generated_automations": s.get("generated_automations", []),
        "errors": s.get("errors", []),
    }


async def workflow_autonomous_test_plan(
    db: AsyncIOMotorDatabase,
    requirement_id: str,
    *,
    requirements_url: str,
    testcases_url: str,
    generator_url: str,
    auth_headers: dict,
    amount: int = 3,
) -> dict:
    graph = _get_test_plan_graph()
    initial_state = TestPlanState(
        requirement_id=requirement_id,
        requirements_url=requirements_url,
        testcases_url=testcases_url,
        generator_url=generator_url,
        auth_headers=auth_headers,
        amount=amount,
        db=db,
    )
    final_state = await graph.ainvoke(initial_state)
    s = final_state if isinstance(final_state, dict) else final_state.__dict__
    return {
        "requirement_id": s.get("requirement_id", requirement_id),
        "requirement_title": s.get("requirement_title", ""),
        "started_at": s.get("started_at", ""),
        "completed_at": s.get("completed_at", ""),
        "existing_testcases": s.get("existing_testcases", 0),
        "generated_testcases": s.get("generated_testcases", []),
        "errors": s.get("errors", []),
    }


async def workflow_batch_execute(
    db: AsyncIOMotorDatabase,
    test_case_ids: list[str],
    *,
    generator_url: str,
    auth_headers: dict,
) -> dict:
    graph = _get_batch_execute_graph()
    initial_state = BatchExecuteState(
        test_case_ids=test_case_ids,
        generator_url=generator_url,
        auth_headers=auth_headers,
        db=db,
    )
    final_state = await graph.ainvoke(initial_state)
    s = final_state if isinstance(final_state, dict) else final_state.__dict__
    return {
        "started_at": s.get("started_at", ""),
        "completed_at": s.get("completed_at", ""),
        "total": len(test_case_ids),
        "succeeded": s.get("succeeded", 0),
        "failed": s.get("failed", 0),
        "results": s.get("results", []),
        "errors": s.get("errors", []),
    }
