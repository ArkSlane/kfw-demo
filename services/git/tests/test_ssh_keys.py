"""
Tests for SSH key management functionality.
"""
import pytest
from pathlib import Path
import stat
import os
import platform


@pytest.mark.asyncio
async def test_upload_ssh_key_success(client, ssh_keys_dir, valid_private_key, valid_public_key):
    """Test successfully uploading a valid SSH key."""
    payload = {
        "key_name": "github_deploy",
        "private_key": valid_private_key,
        "public_key": valid_public_key
    }

    response = await client.post("/ssh-keys", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert data["key_name"] == "github_deploy"
    assert "fingerprint" in data
    assert data["has_public_key"] is True
    assert data["path"] == str(ssh_keys_dir / "github_deploy")

    # Verify files were created
    private_key_path = ssh_keys_dir / "github_deploy"
    public_key_path = ssh_keys_dir / "github_deploy.pub"

    assert private_key_path.exists()
    assert public_key_path.exists()

    # Skip permission check on Windows (permissions work differently)
    if platform.system() != "Windows":
        private_key_stat = os.stat(private_key_path)
        mode = stat.S_IMODE(private_key_stat.st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


@pytest.mark.asyncio
async def test_upload_ssh_key_without_public_key(client, ssh_keys_dir, valid_private_key):
    """Test uploading SSH key without public key."""
    payload = {
        "key_name": "gitlab_deploy",
        "private_key": valid_private_key
    }
    
    response = await client.post("/ssh-keys", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["key_name"] == "gitlab_deploy"
    assert data["has_public_key"] is False
    
    # Verify only private key was created
    private_key_path = ssh_keys_dir / "gitlab_deploy"
    public_key_path = ssh_keys_dir / "gitlab_deploy.pub"
    
    assert private_key_path.exists()
    assert not public_key_path.exists()


@pytest.mark.asyncio
async def test_upload_ssh_key_invalid_name(client, valid_private_key):
    """Test uploading SSH key with invalid name containing special characters."""
    payload = {
        "key_name": "github/deploy",  # Contains /
        "private_key": valid_private_key
    }
    
    response = await client.post("/ssh-keys", json=payload)
    
    assert response.status_code == 400
    data = response.json()
    assert "alphanumeric" in data["message"].lower()


@pytest.mark.asyncio
async def test_upload_ssh_key_invalid_format(client, invalid_private_key):
    """Test uploading SSH key with invalid format."""
    payload = {
        "key_name": "invalid_key",
        "private_key": invalid_private_key
    }
    
    response = await client.post("/ssh-keys", json=payload)
    
    assert response.status_code == 400
    data = response.json()
    assert "invalid private key format" in data["message"].lower()


@pytest.mark.asyncio
async def test_upload_ssh_key_duplicate(client, valid_private_key):
    """Test uploading a duplicate SSH key."""
    payload = {
        "key_name": "duplicate_key",
        "private_key": valid_private_key
    }
    
    # Upload first time
    response1 = await client.post("/ssh-keys", json=payload)
    assert response1.status_code == 200
    
    # Try to upload again with same name
    response2 = await client.post("/ssh-keys", json=payload)
    assert response2.status_code == 409
    data = response2.json()
    assert "already exists" in data["message"]


@pytest.mark.asyncio
async def test_list_ssh_keys_empty(client):
    """Test listing SSH keys when none exist."""
    response = await client.get("/ssh-keys")
    
    assert response.status_code == 200
    data = response.json()
    
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_list_ssh_keys_multiple(client, valid_private_key, valid_public_key):
    """Test listing multiple SSH keys."""
    # Upload multiple keys
    keys = ["key1", "key2", "key3"]
    
    for key_name in keys:
        payload = {
            "key_name": key_name,
            "private_key": valid_private_key,
            "public_key": valid_public_key
        }
        response = await client.post("/ssh-keys", json=payload)
        assert response.status_code == 200
    
    # List all keys
    response = await client.get("/ssh-keys")
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 3
    
    # Check each key has required fields
    for key_info in data:
        assert "key_name" in key_info
        assert "fingerprint" in key_info
        assert "has_public_key" in key_info
        assert "path" in key_info
        assert key_info["key_name"] in keys


@pytest.mark.asyncio
async def test_get_ssh_key_details(client, valid_private_key, valid_public_key):
    """Test getting details of a specific SSH key."""
    # Upload a key
    payload = {
        "key_name": "test_key",
        "private_key": valid_private_key,
        "public_key": valid_public_key
    }
    upload_response = await client.post("/ssh-keys", json=payload)
    assert upload_response.status_code == 200
    
    # Get key details
    response = await client.get("/ssh-keys/test_key")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["key_name"] == "test_key"
    assert "fingerprint" in data
    assert data["has_public_key"] is True
    assert "public_key" in data
    assert data["public_key"].startswith("ssh-rsa")
    assert "path" in data


@pytest.mark.asyncio
async def test_get_ssh_key_not_found(client):
    """Test getting details of non-existent SSH key."""
    response = await client.get("/ssh-keys/nonexistent_key")
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["message"].lower()


@pytest.mark.asyncio
async def test_delete_ssh_key(client, valid_private_key, ssh_keys_dir):
    """Test deleting an SSH key."""
    # Upload a key
    payload = {
        "key_name": "delete_me",
        "private_key": valid_private_key
    }
    upload_response = await client.post("/ssh-keys", json=payload)
    assert upload_response.status_code == 200
    
    # Verify key exists
    key_path = ssh_keys_dir / "delete_me"
    assert key_path.exists()
    
    # Delete the key
    response = await client.delete("/ssh-keys/delete_me")
    
    assert response.status_code == 200
    data = response.json()
    assert data["key_name"] == "delete_me"
    assert data["deleted"] is True
    
    # Verify key was removed
    assert not key_path.exists()


@pytest.mark.asyncio
async def test_delete_ssh_key_with_public_key(client, valid_private_key, valid_public_key, ssh_keys_dir):
    """Test deleting an SSH key that has both private and public keys."""
    # Upload a key with public key
    payload = {
        "key_name": "delete_both",
        "private_key": valid_private_key,
        "public_key": valid_public_key
    }
    upload_response = await client.post("/ssh-keys", json=payload)
    assert upload_response.status_code == 200
    
    # Verify both keys exist
    private_key_path = ssh_keys_dir / "delete_both"
    public_key_path = ssh_keys_dir / "delete_both.pub"
    assert private_key_path.exists()
    assert public_key_path.exists()
    
    # Delete the key
    response = await client.delete("/ssh-keys/delete_both")
    
    assert response.status_code == 200
    
    # Verify both keys were removed
    assert not private_key_path.exists()
    assert not public_key_path.exists()


@pytest.mark.asyncio
async def test_delete_ssh_key_not_found(client):
    """Test deleting a non-existent SSH key."""
    response = await client.delete("/ssh-keys/nonexistent_key")
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["message"].lower()
