"""
Tests for updating releases.
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_update_release_name(client, sample_release):
    """Test updating release name."""
    release_id = str(sample_release["_id"])
    payload = {"name": "Updated Release Name"}
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "Updated Release Name"
    assert data["id"] == release_id


@pytest.mark.asyncio
async def test_update_release_description(client, sample_release):
    """Test updating release description."""
    release_id = str(sample_release["_id"])
    payload = {"description": "New description"}
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["description"] == "New description"


@pytest.mark.asyncio
async def test_update_release_dates(client, sample_release):
    """Test updating release dates."""
    release_id = str(sample_release["_id"])
    payload = {
        "from_date": "2025-06-01T00:00:00Z",
        "to_date": "2025-08-31T23:59:59Z"
    }
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["from_date"].startswith("2025-06-01T00:00:00")
    assert data["to_date"].startswith("2025-08-31T23:59:59")


@pytest.mark.asyncio
async def test_update_release_requirement_ids(client, sample_release):
    """Test updating requirement IDs."""
    release_id = str(sample_release["_id"])
    payload = {"requirement_ids": ["new_req1", "new_req2", "new_req3"]}
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["requirement_ids"] == ["new_req1", "new_req2", "new_req3"]


@pytest.mark.asyncio
async def test_update_release_testcase_ids(client, sample_release):
    """Test updating testcase IDs."""
    release_id = str(sample_release["_id"])
    payload = {"testcase_ids": ["new_tc1"]}
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["testcase_ids"] == ["new_tc1"]


@pytest.mark.asyncio
async def test_update_release_multiple_fields(client, sample_release):
    """Test updating multiple fields at once."""
    release_id = str(sample_release["_id"])
    payload = {
        "name": "Multi-Update Release",
        "description": "Updated multiple fields",
        "requirement_ids": ["req_a", "req_b"],
        "testcase_ids": ["tc_x", "tc_y", "tc_z"]
    }
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "Multi-Update Release"
    assert data["description"] == "Updated multiple fields"
    assert data["requirement_ids"] == ["req_a", "req_b"]
    assert data["testcase_ids"] == ["tc_x", "tc_y", "tc_z"]


@pytest.mark.asyncio
async def test_update_release_not_found(client):
    """Test updating a non-existent release returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    payload = {"name": "Updated"}
    
    response = await client.put(f"/releases/{fake_id}", json=payload)
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_release_invalid_id(client):
    """Test updating with invalid ID format returns 400."""
    invalid_id = "invalid-id"
    payload = {"name": "Updated"}
    
    response = await client.put(f"/releases/{invalid_id}", json=payload)
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_release_empty_payload(client, sample_release):
    """Test updating with no fields returns 400."""
    release_id = str(sample_release["_id"])
    payload = {}
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "message" in data
    assert "no fields" in data["message"].lower()


@pytest.mark.asyncio
async def test_update_release_null_values_ignored(client, sample_release, db):
    """Test that null values in update payload are ignored."""
    release_id = str(sample_release["_id"])
    
    # Update with null values (should be ignored)
    payload = {
        "name": "New Name",
        "description": None,
        "requirement_ids": None
    }
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    # Name should be updated
    assert data["name"] == "New Name"
    
    # Description should retain original value (not set to null)
    assert data["description"] == sample_release["description"]
    
    # requirement_ids should retain original value
    assert data["requirement_ids"] == sample_release["requirement_ids"]


@pytest.mark.asyncio
async def test_update_release_updates_timestamp(client, sample_release):
    """Test that updated_at timestamp is changed on update."""
    release_id = str(sample_release["_id"])
    original_updated_at = sample_release["updated_at"]
    
    # Small delay to ensure timestamp difference
    import asyncio
    await asyncio.sleep(0.1)
    
    payload = {"name": "Updated Name"}
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    updated_str = data["updated_at"].replace("Z", "+00:00")
    new_updated_at = datetime.fromisoformat(updated_str)
    if new_updated_at.tzinfo is None:
        new_updated_at = new_updated_at.replace(tzinfo=timezone.utc)
    
    assert new_updated_at > original_updated_at


@pytest.mark.asyncio
async def test_update_release_preserves_created_at(client, sample_release):
    """Test that created_at is not changed on update."""
    release_id = str(sample_release["_id"])
    original_created_at = sample_release["created_at"]
    
    payload = {"name": "Updated Name"}
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    created_str = data["created_at"].replace("Z", "+00:00")
    updated_created_at = datetime.fromisoformat(created_str)
    if updated_created_at.tzinfo is None:
        updated_created_at = updated_created_at.replace(tzinfo=timezone.utc)
    
    # Should be same time (within microseconds)
    assert abs((updated_created_at - original_created_at).total_seconds()) < 0.001


@pytest.mark.asyncio
async def test_update_release_clear_lists(client, sample_release):
    """Test updating lists to empty arrays."""
    release_id = str(sample_release["_id"])
    payload = {
        "requirement_ids": [],
        "testcase_ids": []
    }
    
    response = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["requirement_ids"] == []
    assert data["testcase_ids"] == []
