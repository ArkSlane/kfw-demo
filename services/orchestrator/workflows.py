"""
Autonomous workflows that coordinate multiple services.

Each workflow is an async function that:
  1. Plans actions based on the current state
  2. Executes actions across services (requirements, testcases, generator, etc.)
  3. Observes results and decides next steps
  4. Persists outcomes and learnings

Workflows are triggered via the orchestrator API or scheduled tasks.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from agent_memory import record_generation_outcome

logger = logging.getLogger(__name__)


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
    """Analyse a release, find coverage gaps, and optionally generate missing tests.

    Steps:
      1. Fetch release → get requirement_ids
      2. For each requirement, fetch linked test cases
      3. Identify requirements with no test cases (coverage gaps)
      4. Optionally: generate test cases for uncovered requirements
      5. Optionally: generate + execute automations for new test cases
      6. Return a coverage report

    Returns a structured report dict.
    """
    report: dict = {
        "release_id": release_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "requirements_total": 0,
        "requirements_covered": 0,
        "requirements_uncovered": 0,
        "coverage_pct": 0.0,
        "gaps": [],
        "generated_testcases": [],
        "generated_automations": [],
        "errors": [],
    }

    async with httpx.AsyncClient(timeout=120, headers=auth_headers) as client:
        # Step 1: Fetch all requirements for this release
        try:
            resp = await client.get(f"{requirements_url}/requirements", params={"release_id": release_id})
            resp.raise_for_status()
            requirements = resp.json() if isinstance(resp.json(), list) else resp.json().get("items", resp.json().get("requirements", []))
        except Exception as e:
            report["errors"].append(f"Failed to fetch requirements: {e}")
            return report

        report["requirements_total"] = len(requirements)

        # Step 2: For each requirement, check test case coverage
        for req in requirements:
            req_id = req.get("id") or str(req.get("_id", ""))
            req_title = req.get("title", "Untitled")
            try:
                tc_resp = await client.get(
                    f"{testcases_url}/testcases",
                    params={"requirement_id": req_id},
                )
                tc_resp.raise_for_status()
                tc_data = tc_resp.json()
                testcases = tc_data if isinstance(tc_data, list) else tc_data.get("items", tc_data.get("testcases", []))
            except Exception as e:
                report["errors"].append(f"Failed to check coverage for req {req_id}: {e}")
                testcases = []

            if testcases:
                report["requirements_covered"] += 1
            else:
                report["requirements_uncovered"] += 1
                gap = {"requirement_id": req_id, "title": req_title}
                report["gaps"].append(gap)

                # Step 3: Optionally auto-generate test cases
                if auto_generate:
                    try:
                        gen_resp = await client.post(
                            f"{generator_url}/generate-structured-testcase",
                            json={"requirement_id": req_id},
                            timeout=180,
                        )
                        gen_resp.raise_for_status()
                        gen_data = gen_resp.json()
                        tc_id = gen_data.get("testcase_id") or gen_data.get("id")
                        gap["generated_testcase_id"] = tc_id
                        report["generated_testcases"].append(tc_id)
                        logger.info("Generated testcase %s for requirement %s", tc_id, req_id)

                        # Step 4: Optionally auto-generate and execute automation
                        if auto_execute and tc_id:
                            t0 = time.monotonic()
                            try:
                                auto_resp = await client.post(
                                    f"{generator_url}/generate-automation-from-execution",
                                    json={"test_case_id": tc_id},
                                    timeout=300,
                                )
                                auto_resp.raise_for_status()
                                auto_data = auto_resp.json()
                                duration_ms = int((time.monotonic() - t0) * 1000)
                                gap["automation_id"] = auto_data.get("automation_id") or auto_data.get("id")
                                gap["automation_status"] = auto_data.get("status")
                                report["generated_automations"].append(gap["automation_id"])

                                # Record outcome to agent memory
                                await record_generation_outcome(
                                    db,
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
                                report["errors"].append(f"Automation failed for tc {tc_id}: {e}")
                    except Exception as e:
                        report["errors"].append(f"Generation failed for req {req_id}: {e}")

        total = report["requirements_total"] or 1
        report["coverage_pct"] = round(report["requirements_covered"] / total * 100, 1)
        report["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Persist the report
    report_doc = {**report, "type": "workflow_report", "workflow": "release_coverage"}
    await db["orchestrator_reports"].insert_one(report_doc)

    return report


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
    """When a requirement is created/updated, proactively generate test cases.

    Steps:
      1. Fetch the requirement
      2. Check if test cases already exist
      3. If none, generate N test cases
      4. Return the plan

    This can be wired to a webhook or called manually.
    """
    report: dict = {
        "requirement_id": requirement_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "existing_testcases": 0,
        "generated_testcases": [],
        "errors": [],
    }

    async with httpx.AsyncClient(timeout=120, headers=auth_headers) as client:
        # Fetch requirement
        try:
            resp = await client.get(f"{requirements_url}/requirements/{requirement_id}")
            resp.raise_for_status()
            requirement = resp.json()
        except Exception as e:
            report["errors"].append(f"Failed to fetch requirement: {e}")
            return report

        report["requirement_title"] = requirement.get("title", "")

        # Check existing test cases
        try:
            tc_resp = await client.get(
                f"{testcases_url}/testcases",
                params={"requirement_id": requirement_id},
            )
            tc_resp.raise_for_status()
            tc_data = tc_resp.json()
            existing = tc_data if isinstance(tc_data, list) else tc_data.get("items", tc_data.get("testcases", []))
            report["existing_testcases"] = len(existing)
        except Exception:
            existing = []

        # Generate test cases if none exist
        if not existing:
            try:
                gen_resp = await client.post(
                    f"{generator_url}/generate",
                    json={"requirement_id": requirement_id, "amount": amount},
                    timeout=180,
                )
                gen_resp.raise_for_status()
                gen_data = gen_resp.json()
                generated = gen_data.get("generated", [])
                report["generated_testcases"] = [tc.get("id", "") for tc in generated]
                logger.info(
                    "Auto-generated %d testcases for requirement %s",
                    len(generated), requirement_id,
                )
            except Exception as e:
                report["errors"].append(f"Generation failed: {e}")
        else:
            logger.info(
                "Requirement %s already has %d testcases, skipping",
                requirement_id, len(existing),
            )

        report["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Persist
    report_doc = {**report, "type": "workflow_report", "workflow": "autonomous_test_plan"}
    await db["orchestrator_reports"].insert_one(report_doc)

    return report


async def workflow_batch_execute(
    db: AsyncIOMotorDatabase,
    test_case_ids: list[str],
    *,
    generator_url: str,
    auth_headers: dict,
) -> dict:
    """Execute automations for a batch of test cases sequentially.

    Useful for regression testing: run all automations for a release's test cases
    and collect results.
    """
    report: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total": len(test_case_ids),
        "succeeded": 0,
        "failed": 0,
        "results": [],
        "errors": [],
    }

    async with httpx.AsyncClient(timeout=300, headers=auth_headers) as client:
        for tc_id in test_case_ids:
            t0 = time.monotonic()
            result = {"test_case_id": tc_id}
            try:
                resp = await client.post(
                    f"{generator_url}/generate-automation-from-execution",
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
                    report["succeeded"] += 1
                else:
                    report["failed"] += 1

                await record_generation_outcome(
                    db,
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
                report["failed"] += 1
                result["error"] = str(e)
                report["errors"].append(f"Execution failed for tc {tc_id}: {e}")

            report["results"].append(result)

    report["completed_at"] = datetime.now(timezone.utc).isoformat()

    report_doc = {**report, "type": "workflow_report", "workflow": "batch_execute"}
    await db["orchestrator_reports"].insert_one(report_doc)

    return report
