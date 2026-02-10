"""
Tests for the /push-test-to-git endpoint in Generator service.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


def make_response(status_code: int, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    # httpx.Response.raise_for_status() is synchronous
    resp.raise_for_status = MagicMock()
    return resp


@pytest_asyncio.fixture
async def client():
    """Create test client for generator service."""
    # Import after setting env vars
    from main import app
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_success(client):
    """Test successful push-test-to-git endpoint call."""
    # Mock dependencies
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock test case fetch + automations fetch (no existing automation) + automations fetch after save
        get_responses = [
            make_response(200, {
                "id": "test123",
                "title": "User Login Test",
                "metadata": {
                    "description": "Test user login flow",
                    "preconditions": "User exists",
                    "steps": [
                        {"action": "Navigate to login", "expected_result": "Page loads"},
                        {"action": "Enter credentials", "expected_result": "Form filled"}
                    ]
                }
            }),
            make_response(200, []),
            make_response(200, [{
                "id": "auto123",
                "script": "await page.goto('/login');"
            }]),
        ]
        mock_client.get.side_effect = get_responses
        
        # Mock automation generation
        with patch('main.generate_automation_with_ollama') as mock_generate:
            mock_generate.return_value = "await page.goto('/login');\nawait page.click('#login-btn');"
            
            # Mock automation save
            mock_client.post.side_effect = [
                # Save automation
                make_response(200, {"id": "auto123"}),
                # (no more post calls expected here)
            ]
            
            # Mock push_test_to_git
            with patch('main.push_test_to_git') as mock_push:
                mock_push.return_value = {
                    "success": True,
                    "pr_url": "https://github.com/org/repo/pull/42",
                    "pr_number": 42,
                    "branch_name": "feat/test-test123-1234567890",
                    "file_path": "tests/generated/user-login-test.spec.js",
                    "repo_name": "tests",
                    "cloned": True
                }
                
                # Make request
                response = await client.post(
                    "/push-test-to-git",
                    json={
                        "test_case_id": "test123",
                        "provider": "github"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert data["test_case_id"] == "test123"
                assert data["automation_id"] == "auto123"
                assert data["git_result"]["pr_url"] == "https://github.com/org/repo/pull/42"
                assert "execution" in data


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_test_not_found(client):
    """Test endpoint when test case doesn't exist."""
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock 404 response
        mock_client.get.return_value = make_response(404, None)
        
        response = await client.post(
            "/push-test-to-git",
            json={
                "test_case_id": "nonexistent",
                "provider": "github"
            }
        )
        
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_uses_existing_automation(client):
    """Test endpoint uses existing automation if available."""
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Mock test case fetch
        mock_client.get.side_effect = [
            make_response(200, {
                "id": "test123",
                "title": "Existing Test",
                "metadata": {}
            }),
            make_response(200, [{
                "id": "existing_auto123",
                "script": "await page.goto('/existing');"
            }])
        ]
        
        # Mock push_test_to_git
        with patch('main.push_test_to_git') as mock_push:
            mock_push.return_value = {
                "success": True,
                "pr_url": "https://github.com/org/repo/pull/1",
                "pr_number": 1,
                "branch_name": "feat/test-test123-1234567890",
                "file_path": "tests/generated/test.spec.js",
                "repo_name": "tests",
                "cloned": False
            }
            
            response = await client.post(
                "/push-test-to-git",
                json={
                    "test_case_id": "test123",
                    "provider": "github"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should use existing automation ID
            assert data["automation_id"] == "existing_auto123"
            
            # Verify push_test_to_git was called with existing script
            mock_push.assert_called_once()
            call_kwargs = mock_push.call_args[1]
            assert call_kwargs["script_content"] == "await page.goto('/existing');"


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_with_ssh_key(client):
    """Test endpoint with SSH key parameter."""
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Setup mocks
        mock_client.get.side_effect = [
            make_response(200, {
                "id": "test123",
                "title": "Test",
                "metadata": {}
            }),
            make_response(200, [{
                "id": "auto123",
                "script": "await page.goto('/');"
            }])
        ]
        
        with patch('main.push_test_to_git') as mock_push:
            mock_push.return_value = {
                "success": True,
                "pr_url": "https://github.com/org/repo/pull/1",
                "pr_number": 1,
                "branch_name": "feat/test-test123-1234567890",
                "file_path": "tests/generated/test.spec.js",
                "repo_name": "tests",
                "cloned": True
            }
            
            response = await client.post(
                "/push-test-to-git",
                json={
                    "test_case_id": "test123",
                    "provider": "github",
                    "ssh_key_name": "my-ssh-key"
                }
            )
            
            assert response.status_code == 200
            
            # Verify SSH key was passed to push_test_to_git
            mock_push.assert_called_once()
            call_kwargs = mock_push.call_args[1]
            assert call_kwargs["ssh_key_name"] == "my-ssh-key"


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_missing_repo_url(client):
    """Test endpoint fails gracefully when repo URL not configured."""
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_client.get.side_effect = [
            make_response(200, {
                "id": "test123",
                "title": "Test",
                "metadata": {}
            }),
            make_response(200, [{
                "id": "auto123",
                "script": "await page.goto('/');"
            }])
        ]
        
        # Mock push_test_to_git to raise ValueError
        with patch('main.push_test_to_git') as mock_push:
            mock_push.side_effect = ValueError("TESTS_REPO_URL environment variable not set")
            
            response = await client.post(
                "/push-test-to-git",
                json={
                    "test_case_id": "test123",
                    "provider": "github"
                }
            )
            
            assert response.status_code == 400
            body = response.json()
            assert "TESTS_REPO_URL" in (body.get("message") or "")


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_with_custom_repo_url(client):
    """Test endpoint with custom repo URL override."""
    with patch('main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        mock_client.get.side_effect = [
            make_response(200, {
                "id": "test123",
                "title": "Test",
                "metadata": {}
            }),
            make_response(200, [{
                "id": "auto123",
                "script": "await page.goto('/');"
            }])
        ]
        
        with patch('main.push_test_to_git') as mock_push:
            mock_push.return_value = {
                "success": True,
                "pr_url": "https://github.com/custom/repo/pull/1",
                "pr_number": 1,
                "branch_name": "feat/test-test123-1234567890",
                "file_path": "tests/generated/test.spec.js",
                "repo_name": "custom-repo",
                "cloned": True
            }
            
            custom_repo = "https://github.com/custom/repo.git"
            response = await client.post(
                "/push-test-to-git",
                json={
                    "test_case_id": "test123",
                    "provider": "github",
                    "repo_url": custom_repo
                }
            )
            
            assert response.status_code == 200
            
            # Verify custom repo URL was used
            mock_push.assert_called_once()
            call_kwargs = mock_push.call_args[1]
            assert call_kwargs["repo_url"] == custom_repo


@pytest.mark.asyncio
async def test_push_test_to_git_endpoint_supports_all_providers(client):
    """Test endpoint works with all supported Git providers."""
    for provider in ["github", "gitlab", "azure"]:
        with patch('main.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_client.get.side_effect = [
                make_response(200, {
                    "id": f"test_{provider}",
                    "title": f"Test {provider}",
                    "metadata": {}
                }),
                make_response(200, [{
                    "id": "auto123",
                    "script": "await page.goto('/');"
                }])
            ]
            
            with patch('main.push_test_to_git') as mock_push:
                mock_push.return_value = {
                    "success": True,
                    "pr_url": f"https://{provider}.com/org/repo/pull/1",
                    "pr_number": 1,
                    "branch_name": f"feat/test-test_{provider}-1234567890",
                    "file_path": "tests/generated/test.spec.js",
                    "repo_name": "tests",
                    "cloned": True
                }
                
                response = await client.post(
                    "/push-test-to-git",
                    json={
                        "test_case_id": f"test_{provider}",
                        "provider": provider
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert provider in data["git_result"]["pr_url"]
