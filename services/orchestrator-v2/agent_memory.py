"""
Agent Memory — persistent learning store for the orchestrator (v2).

Unchanged from v1 — the memory layer is framework-agnostic (pure MongoDB).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION = "agent_memory"


# ── Write helpers ────────────────────────────────────────────────────────────

async def record_selector_outcome(
    db: AsyncIOMotorDatabase,
    *,
    page: str,
    selector: str,
    success: bool,
    error_snippet: Optional[str] = None,
    learned_fix: Optional[str] = None,
) -> None:
    key = {"type": "selector_pattern", "page": page, "selector": selector}
    inc_field = "success_count" if success else "failure_count"
    update: dict = {
        "$inc": {inc_field: 1},
        "$set": {"updated_at": datetime.now(timezone.utc)},
        "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
    }
    if error_snippet:
        update["$set"]["last_error"] = error_snippet
    if learned_fix:
        update["$set"]["learned_fix"] = learned_fix
    await db[COLLECTION].update_one(key, update, upsert=True)


async def record_generation_outcome(
    db: AsyncIOMotorDatabase,
    *,
    test_case_id: str,
    requirement_id: Optional[str] = None,
    model: str,
    generation_mode: str,
    first_try_success: bool,
    repair_attempts: int = 0,
    final_success: bool,
    error_type: Optional[str] = None,
    duration_ms: Optional[int] = None,
    page: Optional[str] = None,
) -> None:
    doc = {
        "type": "generation_outcome",
        "test_case_id": test_case_id,
        "requirement_id": requirement_id,
        "model": model,
        "generation_mode": generation_mode,
        "first_try_success": first_try_success,
        "repair_attempts": repair_attempts,
        "final_success": final_success,
        "error_type": error_type,
        "duration_ms": duration_ms,
        "page": page,
        "created_at": datetime.now(timezone.utc),
    }
    await db[COLLECTION].insert_one(doc)


async def record_repair_insight(
    db: AsyncIOMotorDatabase,
    *,
    error_pattern: str,
    fix_description: str,
    page: Optional[str] = None,
    success: bool = True,
) -> None:
    key = {"type": "repair_insight", "error_pattern": error_pattern}
    inc_field = "success_count" if success else "failure_count"
    update: dict = {
        "$inc": {inc_field: 1},
        "$set": {
            "fix_description": fix_description,
            "page": page,
            "updated_at": datetime.now(timezone.utc),
        },
        "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
    }
    await db[COLLECTION].update_one(key, update, upsert=True)


# ── Read helpers ─────────────────────────────────────────────────────────────

async def get_selector_insights(
    db: AsyncIOMotorDatabase,
    page: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    query: dict = {"type": "selector_pattern"}
    if page:
        query["page"] = page
    cursor = db[COLLECTION].find(query, {"_id": 0}).sort("failure_count", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_generation_stats(
    db: AsyncIOMotorDatabase,
    days: int = 7,
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"type": "generation_outcome", "created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "first_try_success": {"$sum": {"$cond": ["$first_try_success", 1, 0]}},
            "final_success": {"$sum": {"$cond": ["$final_success", 1, 0]}},
            "total_repairs": {"$sum": "$repair_attempts"},
            "avg_duration_ms": {"$avg": "$duration_ms"},
        }},
    ]
    results = await db[COLLECTION].aggregate(pipeline).to_list(length=1)
    if not results:
        return {"total": 0, "first_try_success": 0, "final_success": 0,
                "total_repairs": 0, "avg_duration_ms": 0, "first_try_rate": 0, "final_rate": 0}
    r = results[0]
    r.pop("_id", None)
    total = r["total"] or 1
    r["first_try_rate"] = round(r["first_try_success"] / total, 3)
    r["final_rate"] = round(r["final_success"] / total, 3)
    return r


async def get_repair_insights(
    db: AsyncIOMotorDatabase,
    limit: int = 20,
) -> list[dict]:
    cursor = (
        db[COLLECTION]
        .find({"type": "repair_insight"}, {"_id": 0})
        .sort("success_count", -1)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def build_memory_prompt_block(
    db: AsyncIOMotorDatabase,
    page: Optional[str] = None,
) -> str:
    lines: list[str] = []

    selectors = await get_selector_insights(db, page=page, limit=10)
    if selectors:
        lines.append("=== LEARNED SELECTOR PATTERNS ===")
        for s in selectors:
            fc = s.get("failure_count", 0)
            sc = s.get("success_count", 0)
            fix = s.get("learned_fix", "")
            lines.append(
                f"- Page {s.get('page','?')}: selector `{s.get('selector','')}` "
                f"(ok={sc}, fail={fc})"
                + (f" → Fix: {fix}" if fix else "")
            )
        lines.append("")

    repairs = await get_repair_insights(db, limit=8)
    if repairs:
        lines.append("=== LEARNED REPAIR PATTERNS ===")
        for r in repairs:
            lines.append(
                f"- Error: {r.get('error_pattern','?')} → Fix: {r.get('fix_description','?')} "
                f"(worked {r.get('success_count',0)}x)"
            )
        lines.append("")

    stats = await get_generation_stats(db)
    if stats["total"] > 0:
        lines.append("=== GENERATION QUALITY (last 7 days) ===")
        lines.append(
            f"Total: {stats['total']}, First-try success: {stats['first_try_rate']*100:.0f}%, "
            f"Final success: {stats['final_rate']*100:.0f}%, "
            f"Avg repairs: {stats['total_repairs']/stats['total']:.1f}"
        )
        lines.append("")

    return "\n".join(lines) if lines else ""
