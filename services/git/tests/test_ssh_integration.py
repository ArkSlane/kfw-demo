"""
Tests for Git operations with SSH key integration.
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_clone_with_ssh_key(client, valid_private_key):
    """Test cloning repository with SSH key."""
    # Upload SSH key first
    key_payload = {
        "key_name": "test_clone_key",
        "private_key": valid_private_key
    }
    key_response = await client.post("/ssh-keys", json=key_payload)
    assert key_response.status_code == 200
    
    # Mock the git clone command
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Cloned successfully", "", 0)
        
        # Clone repository with SSH key
        clone_payload = {
            "repo_url": "git@github.com:user/repo.git",
            "ssh_key_name": "test_clone_key"
        }
        
        response = await client.post("/clone", json=clone_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_clone_with_nonexistent_ssh_key(client):
    """Test cloning repository with non-existent SSH key."""
    clone_payload = {
        "repo_url": "git@github.com:user/repo.git",
        "ssh_key_name": "nonexistent_key"
    }
    
    response = await client.post("/clone", json=clone_payload)
    
    # Should fail because key doesn't exist
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_push_with_ssh_key(client, valid_private_key, workspace_dir):
    """Test pushing changes with SSH key."""
    # Upload SSH key first
    key_payload = {
        "key_name": "test_push_key",
        "private_key": valid_private_key
    }
    key_response = await client.post("/ssh-keys", json=key_payload)
    assert key_response.status_code == 200
    
    # Create a fake repo directory
    repo_dir = workspace_dir / "test_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    
    # Mock the git push command
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Pushed successfully", "", 0)
        
        # Push with SSH key
        push_payload = {
            "repo_path": "test_repo",
            "ssh_key_name": "test_push_key"
        }
        
        response = await client.post("/push", json=push_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_pull_with_ssh_key(client, valid_private_key, workspace_dir):
    """Test pulling changes with SSH key."""
    # Upload SSH key first
    key_payload = {
        "key_name": "test_pull_key",
        "private_key": valid_private_key
    }
    key_response = await client.post("/ssh-keys", json=key_payload)
    assert key_response.status_code == 200
    
    # Create a fake repo directory
    repo_dir = workspace_dir / "test_repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    
    # Mock the git pull command
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Pulled successfully", "", 0)
        
        # Pull with SSH key
        pull_payload = {
            "repo_path": "test_repo",
            "ssh_key_name": "test_pull_key"
        }
        
        response = await client.post("/pull", json=pull_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_clone_without_ssh_key(client):
    """Test cloning repository without SSH key (HTTPS)."""
    # Mock the git clone command
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Cloned successfully", "", 0)
        
        # Clone repository without SSH key
        clone_payload = {
            "repo_url": "https://github.com/user/repo.git"
        }
        
        response = await client.post("/clone", json=clone_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_ssh_url_validation(client):
    """Test that SSH URLs are accepted by validator."""
    # Mock the git clone command
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Cloned successfully", "", 0)
        
        # Test various SSH URL formats
        ssh_urls = [
            "git@github.com:user/repo.git",
            "git@gitlab.com:user/repo.git",
            "git@bitbucket.org:user/repo.git"
        ]
        
        for ssh_url in ssh_urls:
            clone_payload = {
                "repo_url": ssh_url
            }
            
            response = await client.post("/clone", json=clone_payload)
            
            # Should succeed (validation passes, mocked git command succeeds)
            assert response.status_code == 200, f"Failed for URL: {ssh_url}"


@pytest.mark.asyncio
async def test_invalid_protocol_rejected(client):
    """Test that invalid protocols are rejected."""
    # Test invalid protocols
    invalid_urls = [
        "file:///path/to/repo",
        "ftp://example.com/repo",
        "http://example.com/repo"  # http (not https) should be rejected
    ]
    
    for invalid_url in invalid_urls:
        clone_payload = {
            "repo_url": invalid_url
        }
        
        response = await client.post("/clone", json=clone_payload)
        
        # Should fail validation
        assert response.status_code == 400, f"Should reject URL: {invalid_url}"
        data = response.json()
        assert "protocol" in data["message"].lower()
