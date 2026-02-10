"""
Pytest configuration and fixtures for requirements service tests.
"""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
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
    await database["requirements"].delete_many({})
    
    yield database
    
    # Clean up after test
    await database["requirements"].delete_many({})


@pytest.fixture
async def client(db):
    """Provide an async HTTP client for testing the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def sample_requirement(db):
    """Create a sample requirement for testing."""
    requirement_data = {
        "title": "User Login Feature",
        "description": "Users should be able to log in with email and password",
        "source": "manual",
        "tags": ["authentication", "security"],
        "release_id": "release_123",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db["requirements"].insert_one(requirement_data)
    requirement_data["_id"] = result.inserted_id
    return requirement_data


@pytest.fixture
async def multiple_requirements(db):
    """Create multiple requirements for list/search testing."""
    requirements = [
        {
            "title": "User Registration",
            "description": "Users should be able to register with email",
            "source": "manual",
            "tags": ["authentication"],
            "release_id": "release_123",
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
        {
            "title": "Password Reset",
            "description": "Users should be able to reset their password",
            "source": "jira",
            "tags": ["authentication", "security"],
            "release_id": "release_123",
            "created_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
        },
        {
            "title": "Dashboard Analytics",
            "description": "Admin dashboard should show analytics",
            "source": "code-analysis",
            "tags": ["analytics", "dashboard"],
            "release_id": "release_456",
            "created_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
        },
    ]
    
    result = await db["requirements"].insert_many(requirements)
    for i, requirement in enumerate(requirements):
        requirement["_id"] = result.inserted_ids[i]
    
    return requirements
