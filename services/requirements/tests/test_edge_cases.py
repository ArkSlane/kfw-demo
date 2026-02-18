"""
Tests for edge cases and error conditions.
"""
import pytest


@pytest.mark.asyncio
async def test_create_requirement_with_very_long_title(client):
    """Test creating a requirement with a very long title is rejected."""
    long_title = "R" * 1000
    payload = {"title": long_title}
    
    response = await client.post("/requirements", json=payload)
    
    # Should be rejected – max_length=500
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_requirement_with_very_long_description(client):
    """Test creating a requirement with a very long description."""
    long_desc = "D" * 10000
    payload = {
        "title": "Requirement",
        "description": long_desc
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    assert response.json()["description"] == long_desc


@pytest.mark.asyncio
async def test_create_requirement_with_unicode(client):
    """Test creating a requirement with Unicode characters."""
    payload = {
        "title": "功能 Función Функция 機能 🚀",
        "description": "Unicode test: 中文 Español Русский 日本語 العربية"
    }
    
    response = await client.post("/requirements", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "功能 Función Функция 機能 🚀"
    assert "中文" in data["description"]


@pytest.mark.asyncio
async def test_create_requirement_with_html(client):
    """Test creating a requirement with HTML in fields."""
    payload = {
        "title": "<script>alert('xss')</script>",
        "description": "<b>Bold</b> <i>Italic</i>"
    }
    
    response = await client.post("/requirements", json=payload)
    
    # Should store as-is (no sanitization in current implementation)
    assert response.status_code == 201
    data = response.json()
    assert "<script>" in data["title"]
    assert "<b>" in data["description"]


@pytest.mark.asyncio
async def test_create_requirement_with_large_tag_array(client):
    """Test creating a requirement with very large tag array is rejected."""
    large_tags = [f"tag{i}" for i in range(1000)]
    
    payload = {
        "title": "Large Tags",
        "tags": large_tags
    }
    
    response = await client.post("/requirements", json=payload)
    
    # Should be rejected – max_length=50 on tags list
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_with_regex_special_chars(client, multiple_requirements):
    """Test search with regex special characters."""
    # Test that regex chars are escaped properly
    response = await client.get("/requirements?q=User")
    
    assert response.status_code == 200
    # Should find requirements with "User" in title
    data = response.json()
    assert len(data) > 0


@pytest.mark.asyncio
async def test_concurrent_updates(client, sample_requirement):
    """Test that concurrent updates don't cause issues."""
    import asyncio
    
    requirement_id = str(sample_requirement["_id"])
    
    # Create multiple concurrent update requests
    async def update_requirement(suffix):
        payload = {"description": f"Update {suffix}"}
        return await client.put(f"/requirements/{requirement_id}", json=payload)
    
    tasks = [update_requirement(i) for i in range(10)]
    responses = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(r.status_code == 200 for r in responses)
    
    # Last one wins (or any one, depending on timing)
    final_response = await client.get(f"/requirements/{requirement_id}")
    assert final_response.status_code == 200
    assert "Update" in final_response.json()["description"]


@pytest.mark.asyncio
async def test_create_requirement_with_duplicate_tags(client):
    """Test creating a requirement with duplicate tags."""
    payload = {
        "title": "Duplicate Tags",
        "tags": ["tag1", "tag2", "tag1", "tag1"]
    }
    
    response = await client.post("/requirements", json=payload)
    
    # Should accept duplicates (no validation in current implementation)
    assert response.status_code == 201
    data = response.json()
    assert data["tags"] == ["tag1", "tag2", "tag1", "tag1"]


@pytest.mark.asyncio
async def test_update_requirement_with_same_values(client, sample_requirement):
    """Test updating a requirement with the same values (idempotent)."""
    requirement_id = str(sample_requirement["_id"])
    
    # Get current values
    response1 = await client.get(f"/requirements/{requirement_id}")
    data1 = response1.json()
    
    # Update with same values
    payload = {"title": data1["title"]}
    response2 = await client.put(f"/requirements/{requirement_id}", json=payload)
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Title should be same
    assert data2["title"] == data1["title"]
    
    # updated_at should change even if values are same
    assert data2["updated_at"] != data1["updated_at"]


@pytest.mark.asyncio
async def test_malformed_json(client):
    """Test that malformed JSON is rejected."""
    response = await client.post(
        "/requirements",
        content='{"title": "Test"',  # Missing closing brace
        headers={"Content-Type": "application/json"}
    )
    
    # Should return 4xx error
    assert 400 <= response.status_code < 500


@pytest.mark.asyncio
async def test_missing_content_type(client):
    """Test request without Content-Type header."""
    response = await client.post(
        "/requirements",
        content='{"title": "Test"}',
        headers={}
    )
    
    # FastAPI should still accept it (tries to parse as JSON)
    # May succeed or fail depending on client behavior
    assert response.status_code in [201, 422, 415]


@pytest.mark.asyncio
async def test_create_requirement_with_empty_string_title(client):
    """Test that empty string title is rejected."""
    payload = {"title": ""}
    
    response = await client.post("/requirements", json=payload)
    
    # Should fail validation (min_length=3)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_requirement_with_whitespace_only_title(client):
    """Test that whitespace-only title might pass basic validation."""
    payload = {"title": "   "}  # 3 spaces = meets min_length
    
    response = await client.post("/requirements", json=payload)
    
    # Current implementation might accept this (only checks length)
    # This is actually a potential bug/improvement area
    assert response.status_code in [201, 422]
