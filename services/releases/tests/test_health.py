"""
Tests for health check endpoint.
"""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test that health endpoint returns comprehensive health data."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check required fields
    assert "status" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["service"] == "releases"
    assert "timestamp" in data
    assert "dependencies" in data
    
    # Check MongoDB dependency
    assert "mongodb" in data["dependencies"]
    mongo_check = data["dependencies"]["mongodb"]
    assert "status" in mongo_check
    assert "message" in mongo_check
    assert "response_time_ms" in mongo_check
    assert "database" in mongo_check
