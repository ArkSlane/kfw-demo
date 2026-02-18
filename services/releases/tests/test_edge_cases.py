"""
Tests for edge cases and error conditions.
"""
import pytest


@pytest.mark.asyncio
async def test_create_release_with_very_long_name(client):
    """Test creating a release with a very long name is rejected."""
    long_name = "R" * 1000
    payload = {"name": long_name}
    
    response = await client.post("/releases", json=payload)
    
    # Should be rejected – max_length=200
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_release_with_very_long_description(client):
    """Test creating a release with a very long description."""
    long_desc = "D" * 10000
    payload = {
        "name": "Release",
        "description": long_desc
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    assert response.json()["description"] == long_desc


@pytest.mark.asyncio
async def test_create_release_with_unicode(client):
    """Test creating a release with Unicode characters."""
    payload = {
        "name": "Release 发布 リリース 릴리스 🚀",
        "description": "Unicode test: 中文 日本語 한국어 العربية"
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Release 发布 リリース 릴리스 🚀"
    assert "中文" in data["description"]


@pytest.mark.asyncio
async def test_create_release_with_html(client):
    """Test creating a release with HTML in fields."""
    payload = {
        "name": "<script>alert('xss')</script>",
        "description": "<b>Bold</b> <i>Italic</i>"
    }
    
    response = await client.post("/releases", json=payload)
    
    # Should store as-is (no sanitization in current implementation)
    assert response.status_code == 201
    data = response.json()
    assert "<script>" in data["name"]
    assert "<b>" in data["description"]


@pytest.mark.asyncio
async def test_create_release_with_large_id_arrays(client):
    """Test creating a release with very large ID arrays is rejected."""
    large_req_ids = [f"req{i}" for i in range(1000)]
    large_tc_ids = [f"tc{i}" for i in range(2000)]
    
    payload = {
        "name": "Large Arrays",
        "requirement_ids": large_req_ids,
        "testcase_ids": large_tc_ids
    }
    
    response = await client.post("/releases", json=payload)
    
    # Should be rejected – max_length limits on arrays
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_with_regex_special_chars(client, multiple_releases):
    """Test search with regex special characters."""
    # Test that regex chars are escaped properly
    response = await client.get("/releases?q=1.0")
    
    assert response.status_code == 200
    # Should find releases with "1.0" in name
    data = response.json()
    assert len(data) > 0


@pytest.mark.asyncio
async def test_concurrent_updates(client, sample_release):
    """Test that concurrent updates don't cause issues."""
    import asyncio
    
    release_id = str(sample_release["_id"])
    
    # Create multiple concurrent update requests
    async def update_release(suffix):
        payload = {"description": f"Update {suffix}"}
        return await client.put(f"/releases/{release_id}", json=payload)
    
    tasks = [update_release(i) for i in range(10)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(r.status_code == 200 for r in responses)
    
    # Last one wins (or any one, depending on timing)
    final_response = await client.get(f"/releases/{release_id}")
    assert final_response.status_code == 200
    assert "Update" in final_response.json()["description"]


@pytest.mark.asyncio
async def test_create_release_with_duplicate_ids_in_arrays(client):
    """Test creating a release with duplicate IDs in arrays."""
    payload = {
        "name": "Duplicate IDs",
        "requirement_ids": ["req1", "req2", "req1", "req1"],
        "testcase_ids": ["tc1", "tc1"]
    }
    
    response = await client.post("/releases", json=payload)
    
    # Should accept duplicates (no validation in current implementation)
    assert response.status_code == 201
    data = response.json()
    assert data["requirement_ids"] == ["req1", "req2", "req1", "req1"]


@pytest.mark.asyncio
async def test_update_release_with_same_values(client, sample_release):
    """Test updating a release with the same values (idempotent)."""
    release_id = str(sample_release["_id"])
    
    # Get current values
    response1 = await client.get(f"/releases/{release_id}")
    data1 = response1.json()
    
    # Update with same values
    payload = {"name": data1["name"]}
    response2 = await client.put(f"/releases/{release_id}", json=payload)
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Name should be same
    assert data2["name"] == data1["name"]
    
    # updated_at should change even if values are same
    assert data2["updated_at"] != data1["updated_at"]


@pytest.mark.asyncio
async def test_malformed_json(client):
    """Test that malformed JSON is rejected."""
    response = await client.post(
        "/releases",
        content='{"name": "Test"',  # Missing closing brace
        headers={"Content-Type": "application/json"}
    )
    
    # Should return 4xx error
    assert 400 <= response.status_code < 500


@pytest.mark.asyncio
async def test_missing_content_type(client):
    """Test request without Content-Type header."""
    response = await client.post(
        "/releases",
        content='{"name": "Test"}',
        headers={}
    )
    
    # FastAPI should still accept it (tries to parse as JSON)
    # May succeed or fail depending on client behavior
    assert response.status_code in [201, 422, 415]
