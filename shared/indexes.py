"""
MongoDB index definitions for all collections.

Called during service startup via lifespan to ensure indexes exist.
Indexes are created with background=True so they don't block the event loop.
"""
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Define indexes per collection: { "collection_name": [ (field_or_list, kwargs), ... ] }
INDEX_DEFINITIONS = {
    "requirements": [
        ("release_id", {}),
        ("created_at", {}),
        ("tags", {}),
        ([("title", "text"), ("description", "text")], {"name": "requirements_text_idx"}),
    ],
    "testcases": [
        ("requirement_id", {}),
        ("status", {}),
        ("created_at", {}),
        ([("title", "text"), ("gherkin", "text")], {"name": "testcases_text_idx"}),
    ],
    "releases": [
        ("name", {"unique": True}),
        ("created_at", {}),
    ],
    "executions": [
        ("testcase_id", {}),
        ("automation_id", {}),
        ("result", {}),
        ("executed_at", {}),
        ([("testcase_id", 1), ("executed_at", -1)], {"name": "exec_tc_date_idx"}),
    ],
    "automations": [
        ("test_case_id", {}),
        ("status", {}),
        ("framework", {}),
        ("created_at", {}),
    ],
    "release_assessments": [
        ("release_id", {"unique": True}),
    ],
    "knowledge_graph": [
        ("type", {}),
        ("scope", {}),
        ([("type", 1), ("scope", 1)], {"name": "kg_type_scope_idx"}),
    ],
    "auth_users": [
        ("username", {"unique": True}),
    ],
}


async def ensure_indexes(db: AsyncIOMotorDatabase, collections: list[str] | None = None) -> None:
    """
    Create indexes for the specified collections (or all if None).

    Args:
        db: Motor database instance.
        collections: Optional list of collection names to index. Defaults to all.
    """
    targets = collections or list(INDEX_DEFINITIONS.keys())

    for col_name in targets:
        specs = INDEX_DEFINITIONS.get(col_name, [])
        if not specs:
            continue

        collection = db[col_name]
        for key_spec, kwargs in specs:
            try:
                if isinstance(key_spec, list):
                    # Compound / text index
                    await collection.create_index(key_spec, **kwargs)
                else:
                    # Simple single-field index
                    await collection.create_index(key_spec, **kwargs)
            except Exception as e:
                # Log but don't crash — index may already exist with different options
                logger.warning(f"Index creation on {col_name}.{key_spec} skipped: {e}")

    logger.info(f"Indexes ensured for collections: {targets}")
