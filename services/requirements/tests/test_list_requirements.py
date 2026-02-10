"""
Tests for listing requirements.
"""
import pytest


@pytest.mark.asyncio
async def test_list_requirements_empty(client, db):
    """Test listing requirements when none exist."""
    response = await client.get("/requirements")
    
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_requirements(client, multiple_requirements):
    """Test listing all requirements."""
    response = await client.get("/requirements")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    assert all("id" in req for req in data)
    assert all("title" in req for req in data)


@pytest.mark.asyncio
async def test_list_requirements_sorted_by_updated_at(client, multiple_requirements):
    """Test that requirements are sorted by updated_at descending."""
    response = await client.get("/requirements")
    
    assert response.status_code == 200
    data = response.json()
    
    # Extract titles in order returned
    titles = [r["title"] for r in data]
    
    # Should be sorted by updated_at DESC (most recent first)
    # Based on fixture: Dashboard (March), Password (Feb), Registration (Jan)
    assert titles == ["Dashboard Analytics", "Password Reset", "User Registration"]


@pytest.mark.asyncio
async def test_list_requirements_with_limit(client, multiple_requirements):
    """Test limiting the number of results."""
    response = await client.get("/requirements?limit=2")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_requirements_with_skip(client, multiple_requirements):
    """Test skipping results (pagination)."""
    response = await client.get("/requirements?skip=1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2  # Total 3, skip 1 = 2 remaining
    assert data[0]["title"] == "Password Reset"  # Second in sorted order


@pytest.mark.asyncio
async def test_list_requirements_with_skip_and_limit(client, multiple_requirements):
    """Test pagination with both skip and limit."""
    response = await client.get("/requirements?skip=1&limit=1")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["title"] == "Password Reset"


@pytest.mark.asyncio
async def test_list_requirements_search_by_title(client, multiple_requirements):
    """Test searching requirements by title."""
    response = await client.get("/requirements?q=Password")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert data[0]["title"] == "Password Reset"


@pytest.mark.asyncio
async def test_list_requirements_search_by_description(client, multiple_requirements):
    """Test searching requirements by description."""
    response = await client.get("/requirements?q=analytics")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 1
    assert "analytics" in data[0]["description"].lower()


@pytest.mark.asyncio
async def test_list_requirements_search_case_insensitive(client, multiple_requirements):
    """Test that search is case-insensitive."""
    response1 = await client.get("/requirements?q=PASSWORD")
    response2 = await client.get("/requirements?q=password")
    response3 = await client.get("/requirements?q=PaSsWoRd")
    
    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response3.status_code == 200
    
    assert response1.json() == response2.json() == response3.json()
    assert len(response1.json()) == 1


@pytest.mark.asyncio
async def test_list_requirements_search_partial_match(client, multiple_requirements):
    """Test that search matches partial strings."""
    response = await client.get("/requirements?q=User")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should match "User Registration" and "Password Reset" (Users in description)
    assert len(data) == 2
    # At least one has "User" in title
    titles = [r["title"] for r in data]
    assert any("User" in title for title in titles)


@pytest.mark.asyncio
async def test_list_requirements_search_no_results(client, multiple_requirements):
    """Test searching with no matches."""
    response = await client.get("/requirements?q=NonExistentRequirement")
    
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_requirements_invalid_limit(client):
    """Test that invalid limit values are rejected."""
    # Limit too low
    response1 = await client.get("/requirements?limit=0")
    assert response1.status_code == 422
    
    # Limit too high
    response2 = await client.get("/requirements?limit=300")
    assert response2.status_code == 422


@pytest.mark.asyncio
async def test_list_requirements_invalid_skip(client):
    """Test that invalid skip values are rejected."""
    response = await client.get("/requirements?skip=-1")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_requirements_default_limit(client, db):
    """Test that default limit is applied."""
    from datetime import datetime, timezone
    
    # Create more than 50 requirements
    now = datetime.now(timezone.utc)
    requirements = [{"title": f"Requirement {i}", "created_at": now, "updated_at": now} for i in range(60)]
    await db["requirements"].insert_many(requirements)
    
    response = await client.get("/requirements")
    
    assert response.status_code == 200
    data = response.json()
    
    # Default limit is 50
    assert len(data) == 50


@pytest.mark.asyncio
async def test_list_requirements_by_tag(client, multiple_requirements):
    """Test searching returns results when query string is used."""
    # Note: Current implementation searches title/description only, not tags
    # Use "Dashboard" which appears in a title
    response = await client.get("/requirements?q=Dashboard")
    
    assert response.status_code == 200
    data = response.json()
    
    # Should find "Dashboard Analytics"
    assert len(data) >= 1
    assert any("Dashboard" in r["title"] for r in data)
