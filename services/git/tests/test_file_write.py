"""
Tests for the /file/write endpoint in Git service.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
import os
import importlib


@pytest.fixture(scope="function")
def test_workspace():
    """Create a temporary workspace for tests."""
    workspace = Path(tempfile.mkdtemp(prefix="git_file_write_test_"))
    
    # Set environment variable
    os.environ["WORKSPACE_DIR"] = str(workspace)
    
    yield workspace
    
    # Cleanup
    shutil.rmtree(workspace)


@pytest.fixture
async def client(test_workspace):
    """Create test client for git service."""
    # Import main after setting env vars
    import main as main_module
    importlib.reload(main_module)
    app = main_module.app
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_git_repo(test_workspace):
    """Create a mock git repository in workspace."""
    repo_path = test_workspace / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    
    # Create a simple git config
    git_config = repo_path / ".git" / "config"
    git_config.write_text("[core]\n\trepositoryformatversion = 0\n")
    
    return repo_path


@pytest.mark.asyncio
async def test_file_write_creates_file(client, mock_git_repo):
    """Test that file write endpoint creates a file."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "tests/example.spec.js",
            "content": "import { test } from '@playwright/test';\n\ntest('example', async ({ page }) => {});"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert "tests/example.spec.js" in data["file_path"]
    assert data["size_bytes"] > 0
    
    # Verify file exists
    file_path = mock_git_repo / "tests" / "example.spec.js"
    assert file_path.exists()
    assert file_path.read_text() == "import { test } from '@playwright/test';\n\ntest('example', async ({ page }) => {});"


@pytest.mark.asyncio
async def test_file_write_creates_directories(client, mock_git_repo):
    """Test that file write creates parent directories if they don't exist."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "deep/nested/path/test.spec.js",
            "content": "test content"
        }
    )
    
    assert response.status_code == 200
    
    # Verify nested directories were created
    file_path = mock_git_repo / "deep" / "nested" / "path" / "test.spec.js"
    assert file_path.exists()
    assert file_path.read_text() == "test content"


@pytest.mark.asyncio
async def test_file_write_with_branch_checkout(client, mock_git_repo):
    """Test file write with branch checkout."""
    # Mock git checkout command
    with patch('main.run_git_command') as mock_run:
        mock_run.return_value = ("", "", 0)
        
        response = await client.post(
            "/file/write",
            json={
                "repo_path": "test-repo",
                "file_path": "test.spec.js",
                "content": "test content",
                "branch": "feature-branch"
            }
        )
        
        assert response.status_code == 200
        
        # Verify checkout was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "checkout" in args
        assert "feature-branch" in args


@pytest.mark.asyncio
async def test_file_write_fails_for_nonexistent_repo(client, test_workspace):
    """Test file write fails when repository doesn't exist."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "nonexistent-repo",
            "file_path": "test.spec.js",
            "content": "test content"
        }
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_file_write_fails_for_non_git_directory(client, test_workspace):
    """Test file write fails when directory is not a git repo."""
    # Create non-git directory
    non_git = test_workspace / "not-a-repo"
    non_git.mkdir()
    
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "not-a-repo",
            "file_path": "test.spec.js",
            "content": "test content"
        }
    )
    
    assert response.status_code == 400
    assert "Not a git repository" in response.json()["detail"]


@pytest.mark.asyncio
async def test_file_write_overwrites_existing_file(client, mock_git_repo):
    """Test that file write overwrites existing files."""
    # Create initial file
    test_file = mock_git_repo / "test.spec.js"
    test_file.write_text("original content")
    
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "test.spec.js",
            "content": "new content"
        }
    )
    
    assert response.status_code == 200
    
    # Verify file was overwritten
    assert test_file.read_text() == "new content"


@pytest.mark.asyncio
async def test_file_write_handles_unicode_content(client, mock_git_repo):
    """Test file write handles unicode content correctly."""
    unicode_content = """// Test with Unicode characters
test('login test 测试', async ({ page }) => {
  await page.goto('https://example.com');
  // Comment with emoji 🎉
  await page.click('#button-日本語');
});"""
    
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "unicode-test.spec.js",
            "content": unicode_content
        }
    )
    
    assert response.status_code == 200
    
    # Verify unicode content is preserved
    file_path = mock_git_repo / "unicode-test.spec.js"
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "测试" in content
    assert "🎉" in content
    assert "日本語" in content


@pytest.mark.asyncio
async def test_file_write_prevents_path_traversal(client, mock_git_repo):
    """Test that file write prevents path traversal attacks."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "../../../etc/passwd",
            "content": "malicious content"
        }
    )
    
    # Should either reject or sanitize the path
    # Depending on implementation, could be 400 or 200 with sanitized path
    if response.status_code == 200:
        # Path should be sanitized to stay within repo
        data = response.json()
        file_path = data["file_path"]
        assert ".." not in file_path
        assert "etc/passwd" not in file_path


@pytest.mark.asyncio
async def test_file_write_with_empty_content(client, mock_git_repo):
    """Test file write with empty content."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "empty.spec.js",
            "content": ""
        }
    )
    
    assert response.status_code == 200
    
    # File should exist but be empty
    file_path = mock_git_repo / "empty.spec.js"
    assert file_path.exists()
    assert file_path.read_text() == ""
    assert file_path.stat().st_size == 0


@pytest.mark.asyncio
async def test_file_write_with_large_content(client, mock_git_repo):
    """Test file write handles large files."""
    # Create large content (1MB)
    large_content = "a" * (1024 * 1024)
    
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "large.spec.js",
            "content": large_content
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["size_bytes"] == 1024 * 1024


@pytest.mark.asyncio
async def test_file_write_returns_correct_metadata(client, mock_git_repo):
    """Test that file write returns correct metadata."""
    content = "test content"
    
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "tests/metadata-test.spec.js",
            "content": content
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["file_path"] == "tests/metadata-test.spec.js"
    assert data["size_bytes"] == len(content.encode('utf-8'))
    assert "successfully" in data["message"].lower()


@pytest.mark.asyncio
async def test_file_write_fails_on_checkout_error(client, mock_git_repo):
    """Test file write fails gracefully when branch checkout fails."""
    with patch('main.run_git_command') as mock_run:
        # Simulate checkout failure
        mock_run.return_value = ("", "Branch not found", 1)
        
        response = await client.post(
            "/file/write",
            json={
                "repo_path": "test-repo",
                "file_path": "test.spec.js",
                "content": "test content",
                "branch": "nonexistent-branch"
            }
        )
        
        assert response.status_code == 500
        assert "checkout" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_file_write_with_special_characters_in_path(client, mock_git_repo):
    """Test file write handles special characters in path."""
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "tests/test-file (1).spec.js",
            "content": "test content"
        }
    )
    
    assert response.status_code == 200
    
    # Verify file was created with correct name
    file_path = mock_git_repo / "tests" / "test-file (1).spec.js"
    assert file_path.exists()


@pytest.mark.asyncio
async def test_file_write_preserves_line_endings(client, mock_git_repo):
    """Test that file write preserves different line endings."""
    # Content with mixed line endings
    content_unix = "line1\nline2\nline3"
    content_windows = "line1\r\nline2\r\nline3"
    
    # Write Unix-style
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "unix.spec.js",
            "content": content_unix
        }
    )
    assert response.status_code == 200
    
    # Write Windows-style
    response = await client.post(
        "/file/write",
        json={
            "repo_path": "test-repo",
            "file_path": "windows.spec.js",
            "content": content_windows
        }
    )
    assert response.status_code == 200
    
    # Verify content is preserved
    unix_file = mock_git_repo / "unix.spec.js"
    windows_file = mock_git_repo / "windows.spec.js"
    
    assert unix_file.read_text() == content_unix
    assert windows_file.read_text() == content_windows
