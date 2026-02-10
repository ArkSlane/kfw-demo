"""
Tests for getting individual requirements.
"""
import pytest


@pytest.mark.asyncio
async def test_get_requirement_by_id(client, sample_requirement):
    """Test retrieving a requirement by ID."""
    requirement_id = str(sample_requirement["_id"])
    
    response = await client.get(f"/requirements/{requirement_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == requirement_id
    assert data["title"] == sample_requirement["title"]
    assert data["description"] == sample_requirement["description"]
    assert data["source"] == sample_requirement["source"]
    assert data["tags"] == sample_requirement["tags"]
    assert data["release_id"] == sample_requirement["release_id"]


@pytest.mark.asyncio
async def test_get_requirement_not_found(client):
    """Test getting a non-existent requirement returns 404."""
    fake_id = "507f1f77bcf86cd799439011"  # Valid ObjectId format
    
    response = await client.get(f"/requirements/{fake_id}")
    
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "timestamp" in data
    assert "not found" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_requirement_invalid_id(client):
    """Test getting a requirement with invalid ID format returns 400."""
    invalid_id = "not-a-valid-objectid"
    
    response = await client.get(f"/requirements/{invalid_id}")
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "timestamp" in data
    assert "invalid" in data["message"].lower()


@pytest.mark.asyncio
async def test_get_requirement_empty_id(client):
    """Test getting a requirement with empty ID."""
    response = await client.get("/requirements/")
    
    # Should either be 404 (not found route), 200 (list endpoint), 307 (redirect), or 405 (method not allowed)
    assert response.status_code in [200, 307, 404, 405]


@pytest.mark.asyncio
async def test_get_requirement_includes_all_fields(client, db):
    """Test that GET returns all requirement fields."""
    from datetime import datetime, timezone
    
    requirement_data = {
        "title": "Complete Requirement",
        "description": "Has all fields populated",
        "source": "jira",
        "tags": ["tag1", "tag2", "tag3"],
        "release_id": "rel_123",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db["requirements"].insert_one(requirement_data)
    requirement_id = str(result.inserted_id)
    
    response = await client.get(f"/requirements/{requirement_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "id" in data
    assert "title" in data
    assert "description" in data
    assert "source" in data
    assert "tags" in data
    assert "release_id" in data
    assert "created_at" in data
    assert "updated_at" in data
