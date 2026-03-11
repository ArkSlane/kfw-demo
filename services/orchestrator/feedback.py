"""
Feedback tracking — collects and analyses generation quality over time.

Provides endpoints for:
  - Recording execution outcomes (called by the generator after each run)
  - Querying quality dashboards (first-try rate, failure patterns, trends)
  - Generating improvement suggestions based on accumulated data
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION = "agent_memory"


async def get_failure_breakdown(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> list[dict]:
    """Group failures by error_type over the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {
            "type": "generation_outcome",
            "final_success": False,
            "created_at": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": "$error_type",
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    results = await db[COLLECTION].aggregate(pipeline).to_list(length=20)
    return [{"error_type": r["_id"] or "unknown", "count": r["count"]} for r in results]


async def get_page_difficulty(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> list[dict]:
    """Rank pages by failure rate (hardest pages first)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {
            "type": "generation_outcome",
            "page": {"$ne": None},
            "created_at": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": "$page",
            "total": {"$sum": 1},
            "failures": {"$sum": {"$cond": [{"$not": "$final_success"}, 1, 0]}},
            "avg_repairs": {"$avg": "$repair_attempts"},
        }},
        {"$addFields": {
            "failure_rate": {"$cond": [
                {"$gt": ["$total", 0]},
                {"$divide": ["$failures", "$total"]},
                0,
            ]},
        }},
        {"$sort": {"failure_rate": -1}},
        {"$limit": 20},
    ]
    results = await db[COLLECTION].aggregate(pipeline).to_list(length=20)
    return [
        {
            "page": r["_id"],
            "total": r["total"],
            "failures": r["failures"],
            "failure_rate": round(r.get("failure_rate", 0), 3),
            "avg_repairs": round(r.get("avg_repairs", 0), 1),
        }
        for r in results
    ]


async def get_quality_trend(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> list[dict]:
    """Daily success rate trend over the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {
            "type": "generation_outcome",
            "created_at": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "total": {"$sum": 1},
            "successes": {"$sum": {"$cond": ["$final_success", 1, 0]}},
            "first_try": {"$sum": {"$cond": ["$first_try_success", 1, 0]}},
        }},
        {"$addFields": {
            "success_rate": {"$cond": [
                {"$gt": ["$total", 0]},
                {"$divide": ["$successes", "$total"]},
                0,
            ]},
            "first_try_rate": {"$cond": [
                {"$gt": ["$total", 0]},
                {"$divide": ["$first_try", "$total"]},
                0,
            ]},
        }},
        {"$sort": {"_id": 1}},
    ]
    results = await db[COLLECTION].aggregate(pipeline).to_list(length=60)
    return [
        {
            "date": r["_id"],
            "total": r["total"],
            "successes": r["successes"],
            "first_try": r["first_try"],
            "success_rate": round(r.get("success_rate", 0), 3),
            "first_try_rate": round(r.get("first_try_rate", 0), 3),
        }
        for r in results
    ]


async def suggest_improvements(
    db: AsyncIOMotorDatabase,
    days: int = 14,
) -> list[str]:
    """Analyse recent data and generate text-based improvement suggestions."""
    suggestions: list[str] = []

    # Check overall quality
    from agent_memory import get_generation_stats
    stats = await get_generation_stats(db, days=days)
    if stats["total"] == 0:
        return ["No generation data yet — run some test generations first."]

    if stats["first_try_rate"] < 0.7:
        suggestions.append(
            f"First-try success rate is {stats['first_try_rate']*100:.0f}% (target: >70%). "
            "Consider enriching the knowledge graph with missing pages/selectors."
        )

    if stats["final_rate"] < 0.85:
        suggestions.append(
            f"Final success rate (after repairs) is {stats['final_rate']*100:.0f}% (target: >85%). "
            "Review the most common failure patterns below."
        )

    # Most common failure types
    failures = await get_failure_breakdown(db, days=days)
    for f in failures[:3]:
        suggestions.append(
            f"Error type '{f['error_type']}' caused {f['count']} failures. "
            "Add explicit handling or prompt guidance for this pattern."
        )

    # Hardest pages
    pages = await get_page_difficulty(db, days=days)
    hard_pages = [p for p in pages if p["failure_rate"] > 0.3 and p["total"] >= 3]
    for p in hard_pages[:3]:
        suggestions.append(
            f"Page '{p['page']}' has a {p['failure_rate']*100:.0f}% failure rate "
            f"({p['failures']}/{p['total']}). Update its knowledge graph entry."
        )

    if not suggestions:
        suggestions.append(
            f"Quality looks good: {stats['first_try_rate']*100:.0f}% first-try, "
            f"{stats['final_rate']*100:.0f}% final success rate."
        )

    return suggestions
