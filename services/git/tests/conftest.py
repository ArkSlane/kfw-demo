"""
Pytest configuration and fixtures for Git service tests.
"""
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
import sys
from httpx import AsyncClient, ASGITransport
import os
from unittest.mock import patch, MagicMock

# Ensure repo root is importable (for `shared.*` imports) when running tests locally.
REPO_ROOT = Path(__file__).resolve().parents[3]
GIT_SERVICE_ROOT = Path(__file__).resolve().parents[1]
for p in [str(REPO_ROOT), str(GIT_SERVICE_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Set up test directories
TEST_WORKSPACE = tempfile.mkdtemp(prefix="git_test_workspace_")
TEST_SSH_KEYS = tempfile.mkdtemp(prefix="git_test_ssh_keys_")

os.environ["WORKSPACE_DIR"] = TEST_WORKSPACE
os.environ["SSH_KEYS_DIR"] = TEST_SSH_KEYS

from main import app
from ssh_manager import SSHKeyManager


# Removed custom event_loop fixture - using pytest-asyncio default


@pytest.fixture(scope="function")
def workspace_dir():
    """Provide a clean workspace directory for each test."""
    workspace = Path(TEST_WORKSPACE)
    # Clean up before test
    for item in workspace.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    
    yield workspace
    
    # Clean up after test
    for item in workspace.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


@pytest.fixture(scope="function")
def ssh_keys_dir():
    """Provide a clean SSH keys directory for each test."""
    keys_dir = Path(TEST_SSH_KEYS)
    # Clean up before test
    for item in keys_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            pass
    
    yield keys_dir
    
    # Clean up after test
    for item in keys_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            pass


@pytest.fixture
async def client(workspace_dir, ssh_keys_dir):
    """Provide an async HTTP client for testing the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def ssh_manager(ssh_keys_dir):
    """Provide an SSH key manager instance."""
    return SSHKeyManager(ssh_keys_dir)


@pytest.fixture(autouse=True)
def mock_ssh_keygen():
    """Mock ssh-keygen to always return success. Auto-used for all tests."""
    with patch('ssh_manager.subprocess.run') as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "2048 SHA256:test_fingerprint (RSA)"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def valid_private_key():
    """Provide a valid test SSH private key (RSA) - simple test key."""
    # Simple test key format that won't fail validation
    return "-----BEGIN RSA PRIVATE KEY-----\ntest key content\n-----END RSA PRIVATE KEY-----"


@pytest.fixture
def valid_public_key():
    """Provide a valid test SSH public key."""
    return "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDPxU/FUkpoVCbksy8eBWpGOoNAPy8H2k+o8EfM6pyditi root@localhost"


@pytest.fixture
def invalid_private_key():
    """Provide an invalid SSH private key."""
    return "This is not a valid SSH key"


def pytest_sessionfinish(session, exitstatus):
    """Clean up test directories after all tests complete."""
    try:
        shutil.rmtree(TEST_WORKSPACE)
        shutil.rmtree(TEST_SSH_KEYS)
    except Exception:
        pass
