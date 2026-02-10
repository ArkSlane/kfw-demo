"""
Tests for creating releases.
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_release_minimal(client, db):
    """Test creating a release with only required fields."""
    payload = {
        "name": "Release 1.0"
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "Release 1.0"
    assert data["description"] is None
    assert data["from_date"] is None
    assert data["to_date"] is None
    assert data["requirement_ids"] == []
    assert data["testcase_ids"] == []
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    
    # Verify in database
    doc = await db["releases"].find_one({"name": "Release 1.0"})
    assert doc is not None
    assert doc["name"] == "Release 1.0"


@pytest.mark.asyncio
async def test_create_release_full(client, db):
    """Test creating a release with all fields."""
    payload = {
        "name": "Release 2.0",
        "description": "Major update with new features",
        "from_date": "2025-04-01T00:00:00Z",
        "to_date": "2025-06-30T23:59:59Z",
        "requirement_ids": ["req1", "req2", "req3"],
        "testcase_ids": ["tc1", "tc2", "tc3", "tc4"]
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["name"] == "Release 2.0"
    assert data["description"] == "Major update with new features"
    assert data["from_date"].startswith("2025-04-01T00:00:00")
    assert data["to_date"].startswith("2025-06-30T23:59:59")
    assert data["requirement_ids"] == ["req1", "req2", "req3"]
    assert data["testcase_ids"] == ["tc1", "tc2", "tc3", "tc4"]
    assert "id" in data
    
    # Verify timestamps are set
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_create_release_empty_lists(client):
    """Test creating a release with explicitly empty lists."""
    payload = {
        "name": "Empty Release",
        "requirement_ids": [],
        "testcase_ids": []
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["requirement_ids"] == []
    assert data["testcase_ids"] == []


@pytest.mark.asyncio
async def test_create_release_missing_name(client):
    """Test that creating a release without name fails."""
    payload = {
        "description": "Release without name"
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_release_with_special_characters(client):
    """Test creating a release with special characters in name."""
    payload = {
        "name": "Release v1.0.1-beta+build.123",
        "description": "Test with special chars: @#$%^&*()"
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Release v1.0.1-beta+build.123"
    assert data["description"] == "Test with special chars: @#$%^&*()"


@pytest.mark.asyncio
async def test_create_multiple_releases(client, db):
    """Test creating multiple releases."""
    releases = [
        {"name": "Release 1.0"},
        {"name": "Release 2.0"},
        {"name": "Release 3.0"}
    ]
    
    for payload in releases:
        response = await client.post("/releases", json=payload)
        assert response.status_code == 201
    
    # Verify all in database
    count = await db["releases"].count_documents({})
    assert count == 3


@pytest.mark.asyncio
async def test_create_release_timestamps_are_set(client):
    """Test that created_at and updated_at are automatically set."""
    payload = {"name": "Timestamp Test"}
    
    before = datetime.now(timezone.utc)
    response = await client.post("/releases", json=payload)
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
    
    # Check timestamps are within reasonable range (allow some tolerance for microseconds lost in serialization)
    assert abs((created_at - before).total_seconds()) <= 1
    assert abs((created_at - after).total_seconds()) <= 1
    assert abs((updated_at - before).total_seconds()) <= 1
    assert abs((updated_at - after).total_seconds()) <= 1
    # Times should be very close (within 1 second)
    assert abs((created_at - updated_at).total_seconds()) < 1
