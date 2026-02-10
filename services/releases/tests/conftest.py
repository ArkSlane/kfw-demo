"""
Pytest configuration and fixtures for releases service tests.
"""
import asyncio
import pytest
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os

# Override DB settings for tests
os.environ["MONGO_URI"] = os.getenv("MONGO_TEST_URI", "mongodb://localhost:27017")
os.environ["MONGO_DB_NAME"] = "ai_testing_test"

from main import app
from shared.db import get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db():
    """Provide a clean database for each test."""
    database = get_db()
    
    # Clean up before test
    await database["releases"].delete_many({})
    
    yield database
    
    # Clean up after test
    await database["releases"].delete_many({})


@pytest.fixture
async def client(db):
    """Provide an async HTTP client for testing the API."""
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_release(db):
    """Create a sample release for testing."""
    release_data = {
        "name": "Release 1.0",
        "description": "Initial release",
        "from_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2025, 3, 31, tzinfo=timezone.utc),
        "requirement_ids": ["req1", "req2"],
        "testcase_ids": ["tc1", "tc2", "tc3"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db["releases"].insert_one(release_data)
    release_data["_id"] = result.inserted_id
    return release_data


@pytest.fixture
async def multiple_releases(db):
    """Create multiple releases for list/search testing."""
    releases = [
        {
            "name": "Release 1.0",
            "description": "First major release",
            "from_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "to_date": datetime(2025, 3, 31, tzinfo=timezone.utc),
            "requirement_ids": ["req1"],
            "testcase_ids": ["tc1"],
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
        {
            "name": "Release 2.0",
            "description": "Second major release with new features",
            "from_date": datetime(2025, 4, 1, tzinfo=timezone.utc),
            "to_date": datetime(2025, 6, 30, tzinfo=timezone.utc),
            "requirement_ids": ["req2", "req3"],
            "testcase_ids": ["tc2"],
            "created_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
        },
        {
            "name": "Hotfix 1.0.1",
            "description": "Critical bug fixes",
            "from_date": datetime(2025, 3, 15, tzinfo=timezone.utc),
            "to_date": datetime(2025, 3, 16, tzinfo=timezone.utc),
            "requirement_ids": [],
            "testcase_ids": ["tc3"],
            "created_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
        },
    ]
    
    result = await db["releases"].insert_many(releases)
    for i, release in enumerate(releases):
        release["_id"] = result.inserted_ids[i]
    
    return releases
