"""
Tests for health check endpoint.
"""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test that health endpoint returns ok status."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert data["status"] == "ok"
    assert "timestamp" in data
