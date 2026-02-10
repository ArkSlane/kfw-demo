"""
Tests for creating requirements.
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_requirement_minimal(client, db):
    """Test creating a requirement with only required fields."""
    payload = {
        "title": "User Login"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["title"] == "User Login"
    assert data["description"] is None
    assert data["source"] is None
    assert data["tags"] == []
    assert data["release_id"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    
    # Verify in database
    doc = await db["requirements"].find_one({"title": "User Login"})
    assert doc is not None
    assert doc["title"] == "User Login"


@pytest.mark.asyncio
async def test_create_requirement_full(client, db):
    """Test creating a requirement with all fields."""
    payload = {
        "title": "User Registration Feature",
        "description": "Complete user registration with email verification",
        "source": "manual",
        "tags": ["authentication", "onboarding", "email"],
        "release_id": "release_v1.0"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["title"] == "User Registration Feature"
    assert data["description"] == "Complete user registration with email verification"
    assert data["source"] == "manual"
    assert data["tags"] == ["authentication", "onboarding", "email"]
    assert data["release_id"] == "release_v1.0"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_requirement_with_jira_source(client):
    """Test creating a requirement from JIRA."""
    payload = {
        "title": "API Rate Limiting",
        "description": "Implement rate limiting for API endpoints",
        "source": "jira",
        "tags": ["api", "security"]
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "jira"


@pytest.mark.asyncio
async def test_create_requirement_with_code_analysis_source(client):
    """Test creating a requirement from code analysis."""
    payload = {
        "title": "Error Handling",
        "source": "code-analysis"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "code-analysis"


@pytest.mark.asyncio
async def test_create_requirement_title_too_short(client):
    """Test that creating a requirement with short title fails."""
    payload = {
        "title": "AB"  # Only 2 characters, min is 3
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_requirement_missing_title(client):
    """Test that creating a requirement without title fails."""
    payload = {
        "description": "Requirement without title"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_requirement_with_special_characters(client):
    """Test creating a requirement with special characters in title."""
    payload = {
        "title": "Feature #123: User @Authentication (v2.0)",
        "description": "Test with special chars: !@#$%^&*()"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Feature #123: User @Authentication (v2.0)"


@pytest.mark.asyncio
async def test_create_requirement_empty_tags(client):
    """Test creating a requirement with explicitly empty tags."""
    payload = {
        "title": "Empty Tags Requirement",
        "tags": []
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["tags"] == []


@pytest.mark.asyncio
async def test_create_multiple_requirements(client, db):
    """Test creating multiple requirements."""
    requirements = [
        {"title": "Requirement 1"},
        {"title": "Requirement 2"},
        {"title": "Requirement 3"}
    ]
    
    for payload in requirements:
        response = await client.post("/requirements", json=payload)
        assert response.status_code == 201
    
    # Verify all in database
    count = await db["requirements"].count_documents({})
    assert count == 3


@pytest.mark.asyncio
async def test_create_requirement_timestamps_are_set(client):
    """Test that created_at and updated_at are automatically set."""
    payload = {"title": "Timestamp Test"}
    
    before = datetime.now(timezone.utc)
    response = await client.post("/requirements", json=payload)
    after = datetime.now(timezone.utc)
    
    assert response.status_code == 201
    data = response.json()
    
    created_str = data["created_at"].replace("Z", "+00:00")
    updated_str = data["updated_at"].replace("Z", "+00:00")
    
    # Parse and make timezone-aware if needed
    created_at = datetime.fromisoformat(created_str)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    updated_at = datetime.fromisoformat(updated_str)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    
    # Check timestamps are within reasonable range
    assert abs((created_at - before).total_seconds()) <= 1
    assert abs((created_at - after).total_seconds()) <= 1
    assert abs((updated_at - before).total_seconds()) <= 1
    assert abs((updated_at - after).total_seconds()) <= 1
    # Times should be very close (within 1 second)
    assert abs((created_at - updated_at).total_seconds()) < 1
