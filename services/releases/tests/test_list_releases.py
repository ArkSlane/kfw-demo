"""
Tests for listing releases.
"""
import pytest


@pytest.mark.asyncio
async def test_list_releases_empty(client, db):
    """Test listing releases when none exist."""
    response = await client.get("/releases")
    
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_releases(client, multiple_releases):
    """Test listing all releases."""
    response = await client.get("/releases")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    assert all("id" in release for release in data)
    assert all("name" in release for release in data)


@pytest.mark.asyncio
async def test_list_releases_sorted_by_updated_at(client, multiple_releases):
    """Test that releases are sorted by updated_at descending."""
    response = await client.get("/releases")
    
    assert response.status_code == 200
    data = response.json()
    
    # Extract names in order returned
    names = [r["name"] for r in data]
    
    # Should be sorted by updated_at DESC (most recent first)
    # Based on fixture: Hotfix (March), Release 2.0 (Feb), Release 1.0 (Jan)
    assert names == ["Hotfix 1.0.1", "Release 2.0", "Release 1.0"]


@pytest.mark.asyncio
async def test_list_releases_with_limit(client, multiple_releases):
    """Test limiting the number of results."""
    response = await client.get("/releases?limit=2")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_releases_with_skip(client, multiple_releases):
    """Test skipping results (pagination)."""
    response = await client.get("/releases?skip=1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2  # Total 3, skip 1 = 2 remaining
    assert data[0]["name"] == "Release 2.0"  # Second in sorted order


@pytest.mark.asyncio
async def test_list_releases_with_skip_and_limit(client, multiple_releases):
    """Test pagination with both skip and limit."""
    response = await client.get("/releases?skip=1&limit=1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["name"] == "Release 2.0"


@pytest.mark.asyncio
async def test_list_releases_search_by_name(client, multiple_releases):
    """Test searching releases by name."""
    response = await client.get("/releases?q=Hotfix")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["name"] == "Hotfix 1.0.1"


@pytest.mark.asyncio
async def test_list_releases_search_by_description(client, multiple_releases):
    """Test searching releases by description."""
    response = await client.get("/releases?q=bug")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert "bug" in data[0]["description"].lower()


@pytest.mark.asyncio
async def test_list_releases_search_case_insensitive(client, multiple_releases):
    """Test that search is case-insensitive."""
    response1 = await client.get("/releases?q=HOTFIX")
    response2 = await client.get("/releases?q=hotfix")
    response3 = await client.get("/releases?q=HoTfIx")
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response3.status_code == 200
    
    assert response1.json() == response2.json() == response3.json()
    assert len(response1.json()) == 1


@pytest.mark.asyncio
async def test_list_releases_search_partial_match(client, multiple_releases):
    """Test that search matches partial strings."""
    response = await client.get("/releases?q=Release")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should match "Release 1.0" and "Release 2.0"
    assert len(data) == 2
    assert all("Release" in r["name"] for r in data)


@pytest.mark.asyncio
async def test_list_releases_search_no_results(client, multiple_releases):
    """Test searching with no matches."""
    response = await client.get("/releases?q=NonExistent")
    
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_releases_invalid_limit(client):
    """Test that invalid limit values are rejected."""
    # Limit too low
    response1 = await client.get("/releases?limit=0")
    assert response1.status_code == 422
    
    # Limit too high
    response2 = await client.get("/releases?limit=300")
    assert response2.status_code == 422


@pytest.mark.asyncio
async def test_list_releases_invalid_skip(client):
    """Test that invalid skip values are rejected."""
    response = await client.get("/releases?skip=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_releases_default_limit(client, db):
    """Test that default limit is applied."""
    from datetime import datetime, timezone
    
    # Create more than 50 releases
    now = datetime.now(timezone.utc)
    releases = [{"name": f"Release {i}", "created_at": now, "updated_at": now} for i in range(60)]
    await db["releases"].insert_many(releases)
    
    response = await client.get("/releases")
    
    assert response.status_code == 200
    data = response.json()
    
    # Default limit is 50
    assert len(data) == 50
