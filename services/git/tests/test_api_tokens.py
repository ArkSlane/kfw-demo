import pytest


@pytest.mark.asyncio
async def test_api_tokens_crud(client):
    # Create
    created = (
        await client.post(
            "/api-tokens",
            json={"provider": "github", "name": "ci", "token": "ghp_1234567890abcdef"},
        )
    ).json()

    assert created["provider"] == "github"
    assert created["name"] == "ci"
    assert "id" in created
    assert "token_masked" in created
    assert "token" not in created

    # List
    listed = (await client.get("/api-tokens")).json()
    assert isinstance(listed, list)
    assert any(t["id"] == created["id"] for t in listed)

    # Delete
    resp = await client.delete(f"/api-tokens/{created['id']}")
    assert resp.status_code == 200

    # Ensure deleted
    listed2 = (await client.get("/api-tokens")).json()
    assert not any(t["id"] == created["id"] for t in listed2)
