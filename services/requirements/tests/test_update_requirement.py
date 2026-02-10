"""
Tests for updating requirements.
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_update_requirement_title(client, sample_requirement):
    """Test updating requirement title."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"title": "Updated Login Feature"}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["title"] == "Updated Login Feature"
    assert data["id"] == requirement_id


@pytest.mark.asyncio
async def test_update_requirement_description(client, sample_requirement):
    """Test updating requirement description."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"description": "New detailed description"}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["description"] == "New detailed description"


@pytest.mark.asyncio
async def test_update_requirement_source(client, sample_requirement):
    """Test updating requirement source."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"source": "jira"}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["source"] == "jira"


@pytest.mark.asyncio
async def test_update_requirement_tags(client, sample_requirement):
    """Test updating requirement tags."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"tags": ["new-tag1", "new-tag2", "new-tag3"]}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["tags"] == ["new-tag1", "new-tag2", "new-tag3"]


@pytest.mark.asyncio
async def test_update_requirement_release_id(client, sample_requirement):
    """Test updating requirement release ID."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"release_id": "new_release_456"}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["release_id"] == "new_release_456"


@pytest.mark.asyncio
async def test_update_requirement_multiple_fields(client, sample_requirement):
    """Test updating multiple fields at once."""
    requirement_id = str(sample_requirement["_id"])
    payload = {
        "title": "Multi-Update Feature",
        "description": "Updated multiple fields",
        "source": "code-analysis",
        "tags": ["tag_a", "tag_b"],
        "release_id": "rel_999"
    }
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["title"] == "Multi-Update Feature"
    assert data["description"] == "Updated multiple fields"
    assert data["source"] == "code-analysis"
    assert data["tags"] == ["tag_a", "tag_b"]
    assert data["release_id"] == "rel_999"


@pytest.mark.asyncio
async def test_update_requirement_not_found(client):
    """Test updating a non-existent requirement returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    payload = {"title": "Updated Title"}
    
    response = await client.put(f"/requirements/{fake_id}", json=payload)
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_requirement_invalid_id(client):
    """Test updating with invalid ID format returns 400."""
    invalid_id = "invalid-id"
    payload = {"title": "Updated Title"}
    
    response = await client.put(f"/requirements/{invalid_id}", json=payload)
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_requirement_empty_payload(client, sample_requirement):
    """Test updating with no fields returns 400."""
    requirement_id = str(sample_requirement["_id"])
    payload = {}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "no fields" in data["message"].lower()


@pytest.mark.asyncio
async def test_update_requirement_null_values_ignored(client, sample_requirement, db):
    """Test that null values in update payload are ignored."""
    requirement_id = str(sample_requirement["_id"])
    
    # Update with null values (should be ignored)
    payload = {
        "title": "New Title",
        "description": None,
        "tags": None
    }
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Title should be updated
    assert data["title"] == "New Title"
    
    # Description should retain original value (not set to null)
    assert data["description"] == sample_requirement["description"]
    
    # Tags should retain original value
    assert data["tags"] == sample_requirement["tags"]


@pytest.mark.asyncio
async def test_update_requirement_title_too_short(client, sample_requirement):
    """Test that updating with short title fails validation."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"title": "AB"}  # Only 2 characters, min is 3
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_requirement_updates_timestamp(client, sample_requirement):
    """Test that updated_at timestamp is changed on update."""
    requirement_id = str(sample_requirement["_id"])
    original_updated_at = sample_requirement["updated_at"]
    
    # Small delay to ensure timestamp difference
    import asyncio
    await asyncio.sleep(0.1)
    
    payload = {"title": "Updated Title"}
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    updated_str = data["updated_at"].replace("Z", "+00:00")
    new_updated_at = datetime.fromisoformat(updated_str)
    if new_updated_at.tzinfo is None:
        new_updated_at = new_updated_at.replace(tzinfo=timezone.utc)
    
    assert new_updated_at > original_updated_at


@pytest.mark.asyncio
async def test_update_requirement_preserves_created_at(client, sample_requirement):
    """Test that created_at is not changed on update."""
    requirement_id = str(sample_requirement["_id"])
    original_created_at = sample_requirement["created_at"]
    
    payload = {"title": "Updated Title"}
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    created_str = data["created_at"].replace("Z", "+00:00")
    updated_created_at = datetime.fromisoformat(created_str)
    if updated_created_at.tzinfo is None:
        updated_created_at = updated_created_at.replace(tzinfo=timezone.utc)
    
    # Should be same time (within microseconds)
    assert abs((updated_created_at - original_created_at).total_seconds()) < 0.001


@pytest.mark.asyncio
async def test_update_requirement_clear_tags(client, sample_requirement):
    """Test updating tags to empty array."""
    requirement_id = str(sample_requirement["_id"])
    payload = {"tags": []}
    
    response = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["tags"] == []
