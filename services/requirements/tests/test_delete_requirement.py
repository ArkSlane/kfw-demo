"""
Tests for deleting requirements.
"""
import pytest


@pytest.mark.asyncio
async def test_delete_requirement(client, sample_requirement, db):
    """Test deleting a requirement."""
    requirement_id = str(sample_requirement["_id"])
    
    response = await client.delete(f"/requirements/{requirement_id}")
    
    assert response.status_code == 204
    assert response.content == b""
    
    # Verify deletion in database
    doc = await db["requirements"].find_one({"_id": sample_requirement["_id"]})
    assert doc is None


@pytest.mark.asyncio
async def test_delete_requirement_not_found(client):
    """Test deleting a non-existent requirement returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    
    response = await client.delete(f"/requirements/{fake_id}")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_requirement_invalid_id(client):
    """Test deleting with invalid ID format returns 400."""
    invalid_id = "not-valid-objectid"
    
    response = await client.delete(f"/requirements/{invalid_id}")
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_requirement_twice(client, sample_requirement):
    """Test that deleting the same requirement twice returns 404 on second attempt."""
    requirement_id = str(sample_requirement["_id"])
    
    # First deletion
    response1 = await client.delete(f"/requirements/{requirement_id}")
    assert response1.status_code == 204
    
    # Second deletion should fail
    response2 = await client.delete(f"/requirements/{requirement_id}")
    assert response2.status_code == 404


@pytest.mark.asyncio
async def test_delete_requirement_does_not_affect_others(client, multiple_requirements, db):
    """Test that deleting one requirement doesn't affect others."""
    requirement_id = str(multiple_requirements[0]["_id"])
    
    # Count before deletion
    count_before = await db["requirements"].count_documents({})
    assert count_before == 3
    
    # Delete one requirement
    response = await client.delete(f"/requirements/{requirement_id}")
    assert response.status_code == 204
    
    # Count after deletion
    count_after = await db["requirements"].count_documents({})
    assert count_after == 2
    
    # Verify other requirements still exist
    remaining = await db["requirements"].find().to_list(10)
    remaining_ids = [str(doc["_id"]) for doc in remaining]
    
    assert requirement_id not in remaining_ids
    assert str(multiple_requirements[1]["_id"]) in remaining_ids
    assert str(multiple_requirements[2]["_id"]) in remaining_ids


@pytest.mark.asyncio
async def test_delete_all_requirements(client, multiple_requirements, db):
    """Test deleting all requirements one by one."""
    for requirement in multiple_requirements:
        requirement_id = str(requirement["_id"])
        response = await client.delete(f"/requirements/{requirement_id}")
        assert response.status_code == 204
    
    # Verify all deleted
    count = await db["requirements"].count_documents({})
    assert count == 0


@pytest.mark.asyncio
async def test_delete_and_recreate(client, sample_requirement, db):
    """Test that a requirement can be recreated after deletion."""
    requirement_id = str(sample_requirement["_id"])
    original_title = sample_requirement["title"]
    
    # Delete requirement
    response = await client.delete(f"/requirements/{requirement_id}")
    assert response.status_code == 204
    
    # Create new requirement with same title
    payload = {"title": original_title}
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    # Should have different ID
    assert data["id"] != requirement_id
    assert data["title"] == original_title
