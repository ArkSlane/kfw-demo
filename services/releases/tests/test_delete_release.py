"""
Tests for deleting releases.
"""
import pytest


@pytest.mark.asyncio
async def test_delete_release(client, sample_release, db):
    """Test deleting a release."""
    release_id = str(sample_release["_id"])
    
    response = await client.delete(f"/releases/{release_id}")
    
    assert response.status_code == 204
    assert response.content == b""
    
    # Verify deletion in database
    doc = await db["releases"].find_one({"_id": sample_release["_id"]})
    assert doc is None


@pytest.mark.asyncio
async def test_delete_release_not_found(client):
    """Test deleting a non-existent release returns 404."""
    fake_id = "507f1f77bcf86cd799439011"
    
    response = await client.delete(f"/releases/{fake_id}")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_release_invalid_id(client):
    """Test deleting with invalid ID format returns 400."""
    invalid_id = "not-valid-objectid"
    
    response = await client.delete(f"/releases/{invalid_id}")
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_release_twice(client, sample_release):
    """Test that deleting the same release twice returns 404 on second attempt."""
    release_id = str(sample_release["_id"])
    
    # First deletion
    response1 = await client.delete(f"/releases/{release_id}")
    assert response1.status_code == 204
    
    # Second deletion should fail
    response2 = await client.delete(f"/releases/{release_id}")
    assert response2.status_code == 404


@pytest.mark.asyncio
async def test_delete_release_does_not_affect_others(client, multiple_releases, db):
    """Test that deleting one release doesn't affect others."""
    release_id = str(multiple_releases[0]["_id"])
    
    # Count before deletion
    count_before = await db["releases"].count_documents({})
    assert count_before == 3
    
    # Delete one release
    response = await client.delete(f"/releases/{release_id}")
    assert response.status_code == 204
    
    # Count after deletion
    count_after = await db["releases"].count_documents({})
    assert count_after == 2
    
    # Verify other releases still exist
    remaining = await db["releases"].find().to_list(10)
    remaining_ids = [str(doc["_id"]) for doc in remaining]
    
    assert release_id not in remaining_ids
    assert str(multiple_releases[1]["_id"]) in remaining_ids
    assert str(multiple_releases[2]["_id"]) in remaining_ids


@pytest.mark.asyncio
async def test_delete_all_releases(client, multiple_releases, db):
    """Test deleting all releases one by one."""
    for release in multiple_releases:
        release_id = str(release["_id"])
        response = await client.delete(f"/releases/{release_id}")
        assert response.status_code == 204
    
    # Verify all deleted
    count = await db["releases"].count_documents({})
    assert count == 0


@pytest.mark.asyncio
async def test_delete_and_recreate(client, sample_release, db):
    """Test that a release can be recreated after deletion."""
    release_id = str(sample_release["_id"])
    original_name = sample_release["name"]
    
    # Delete release
    response = await client.delete(f"/releases/{release_id}")
    assert response.status_code == 204
    
    # Create new release with same name
    payload = {"name": original_name}
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    
    # Should have different ID
    assert data["id"] != release_id
    assert data["name"] == original_name
