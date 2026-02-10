"""
Tests for getting individual releases.
"""
import pytest


@pytest.mark.asyncio
async def test_get_release_by_id(client, sample_release):
    """Test retrieving a release by ID."""
    release_id = str(sample_release["_id"])
    
    response = await client.get(f"/releases/{release_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == release_id
    assert data["name"] == sample_release["name"]
    assert data["description"] == sample_release["description"]
    assert data["requirement_ids"] == sample_release["requirement_ids"]
    assert data["testcase_ids"] == sample_release["testcase_ids"]


@pytest.mark.asyncio
async def test_get_release_not_found(client):
    """Test getting a non-existent release returns 404."""
    fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format
    
    response = await client.get(f"/releases/{fake_id}")
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "timestamp" in data
    assert "not found" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_release_invalid_id(client):
    """Test getting a release with invalid ID format returns 400."""
    invalid_id = "not-a-valid-objectid"
    
    response = await client.get(f"/releases/{invalid_id}")
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "timestamp" in data
    assert "invalid" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_release_empty_id(client):
    """Test getting a release with empty ID."""
    response = await client.get("/releases/")
    
    # Should either be 404 (not found route), 200 (list endpoint), 307 (redirect), or 405 (method not allowed)
    assert response.status_code in [200, 307, 404, 405]


@pytest.mark.asyncio
async def test_get_release_includes_all_fields(client, db):
    """Test that GET returns all release fields."""
    from datetime import datetime, timezone
    
    release_data = {
        "name": "Complete Release",
        "description": "Has all fields",
        "from_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "to_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
        "requirement_ids": ["req1", "req2"],
        "testcase_ids": ["tc1", "tc2", "tc3"],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db["releases"].insert_one(release_data)
    release_id = str(result.inserted_id)
    
    response = await client.get(f"/releases/{release_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "id" in data
    assert "name" in data
    assert "description" in data
    assert "from_date" in data
    assert "to_date" in data
    assert "requirement_ids" in data
    assert "testcase_ids" in data
    assert "created_at" in data
    assert "updated_at" in data
