"""
Tests for Git integration functionality in the Generator service.
Tests the git_integration module that pushes generated tests to repositories.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from git_integration import (
    push_test_to_git,
    generate_playwright_test_file,
    trigger_test_execution
)


class TestGeneratePlaywrightTestFile:
    """Tests for Playwright test file generation."""
    
    def test_generate_basic_test_file(self):
        """Test generating a basic Playwright test file."""
        title = "User Login Test"
        script_content = """await page.goto('https://example.com');
await page.click('#login-button');"""
        test_id = "test123"
        
        result = generate_playwright_test_file(title, script_content, test_id)
        
        # Verify file structure
        assert "import { test, expect } from '@playwright/test';" in result
        assert f"test.describe('{title}'" in result
        assert f"test('should execute {title}'" in result
        assert "await page.goto('https://example.com');" in result
        assert "await page.click('#login-button');" in result
        assert f"// Test ID: {test_id}" in result
        assert "// Auto-generated test by AI Test Platform" in result
    
    def test_generate_test_file_with_empty_script(self):
        """Test generating test file with empty script content."""
        title = "Empty Test"
        script_content = ""
        test_id = "empty123"
        
        result = generate_playwright_test_file(title, script_content, test_id)
        
        # Should still generate valid file structure
        assert "import { test, expect } from '@playwright/test';" in result
        assert f"test.describe('{title}'" in result
        assert f"// Test ID: {test_id}" in result
    
    def test_generate_test_file_with_multiline_script(self):
        """Test generating test file with multi-line script."""
        title = "Complex Test"
        script_content = """// Step 1: Navigate
await page.goto('https://example.com');

// Step 2: Fill form
await page.fill('input[name="username"]', 'testuser');
await page.fill('input[name="password"]', 'password123');

// Step 3: Submit
await page.click('button[type="submit"]');"""
        test_id = "complex123"
        
        result = generate_playwright_test_file(title, script_content, test_id)
        
        # Verify indentation is correct
        lines = result.split('\n')
        script_lines = [line for line in lines if 'await page.' in line]
        
        # All script lines should be indented (at least 2 spaces)
        for line in script_lines:
            assert line.startswith('  ')
    
    def test_generate_test_file_with_special_characters_in_title(self):
        """Test generating test file with special characters in title."""
        title = "User's \"Login\" Test & More"
        script_content = "await page.goto('/');"
        test_id = "special123"
        
        result = generate_playwright_test_file(title, script_content, test_id)
        
        # Should handle special characters in title
        assert "User's" in result or "User\\'s" in result
        assert "test.describe(" in result


class TestTriggerTestExecution:
    """Tests for test execution trigger functionality."""
    
    @pytest.mark.asyncio
    async def test_trigger_returns_manual_instructions(self):
        """Test that trigger returns manual execution instructions."""
        branch = "feat/test-abc123-1234567890"
        file_path = "tests/generated/login-test.spec.js"
        repo_name = "test-repo"
        
        result = await trigger_test_execution(branch, file_path, repo_name)
        
        assert result["execution_type"] == "manual"
        assert "instructions" in result
        assert "commands" in result["instructions"]
        assert len(result["instructions"]["commands"]) > 0
        
        # Verify commands contain expected elements
        commands = result["instructions"]["commands"]
        assert any("git checkout" in cmd for cmd in commands)
        assert any("npx playwright test" in cmd for cmd in commands)
    
    @pytest.mark.asyncio
    async def test_trigger_includes_webhook_suggestions(self):
        """Test that trigger includes webhook setup suggestions."""
        result = await trigger_test_execution("branch", "file", "repo")
        
        assert "webhook_suggestion" in result
        assert "github" in result["webhook_suggestion"]
        assert "gitlab" in result["webhook_suggestion"]
        assert "azure" in result["webhook_suggestion"]
    
    @pytest.mark.asyncio
    async def test_trigger_includes_ci_config_examples(self):
        """Test that trigger includes CI config file examples."""
        result = await trigger_test_execution("branch", "file", "repo")
        
        assert "ci_config_examples" in result
        assert "github_actions" in result["ci_config_examples"]
        assert "gitlab_ci" in result["ci_config_examples"]
        assert "azure_pipelines" in result["ci_config_examples"]


class TestPushTestToGit:
    """Tests for the main push_test_to_git workflow."""
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_success_flow(self):
        """Test successful push workflow."""
        # Mock httpx.AsyncClient
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Create mock responses with MagicMock for json() to avoid async issues
            def create_mock_response(data):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json = MagicMock(return_value=data)
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            
            # Mock responses for each step
            mock_client.post.side_effect = [
                # Clone response
                create_mock_response({"success": True}),
                # Branch create response
                create_mock_response({"success": True}),
                # File write response
                create_mock_response({"success": True}),
                # Commit response
                create_mock_response({"success": True}),
                # Push response
                create_mock_response({"success": True}),
                # Merge request response
                create_mock_response({
                    "url": "https://github.com/org/repo/pull/42",
                    "number": 42
                })
            ]
            
            result = await push_test_to_git(
                test_case_id="test123",
                test_title="Login Test",
                script_content="await page.goto('/');",
                provider="github",
                repo_url="https://github.com/org/repo.git"
            )
            
            assert result["success"] is True
            assert result["pr_url"] == "https://github.com/org/repo/pull/42"
            assert result["pr_number"] == 42
            assert "branch_name" in result
            assert "feat/test-test123" in result["branch_name"]
            assert result["file_path"].endswith(".spec.js")
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_missing_repo_url(self):
        """Test push fails when repo URL not provided and not in env."""
        with patch('git_integration.TESTS_REPO_URL', ''):
            with pytest.raises(ValueError, match="TESTS_REPO_URL"):
                await push_test_to_git(
                    test_case_id="test123",
                    test_title="Test",
                    script_content="await page.goto('/');",
                    provider="github"
                )
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_uses_env_variables(self):
        """Test that push uses environment variables when not provided."""
        with patch('git_integration.TESTS_REPO_URL', 'https://github.com/test/repo.git'):
            with patch('git_integration.TESTS_REPO_BRANCH', 'develop'):
                with patch('git_integration.TEST_FILES_PATH', 'e2e/tests'):
                    with patch('git_integration.httpx.AsyncClient') as mock_client_class:
                        mock_client = AsyncMock()
                        mock_client_class.return_value.__aenter__.return_value = mock_client
                        
                        def create_mock_response(data):
                            mock_resp = MagicMock()
                            mock_resp.status_code = 200
                            mock_resp.json = MagicMock(return_value=data)
                            mock_resp.raise_for_status = MagicMock()
                            return mock_resp
                        
                        mock_client.post.side_effect = [
                            create_mock_response({"success": True}),
                            create_mock_response({"success": True}),
                            create_mock_response({"success": True}),
                            create_mock_response({"success": True}),
                            create_mock_response({"success": True}),
                            create_mock_response({
                                "url": "https://github.com/test/repo/pull/1",
                                "number": 1
                            })
                        ]
                        
                        result = await push_test_to_git(
                            test_case_id="test123",
                            test_title="Test",
                            script_content="await page.goto('/');",
                            provider="github"
                        )

                        assert result["success"] is True
                        # File path should use TEST_FILES_PATH env var
                        assert "e2e/tests" in result["file_path"]
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_with_ssh_key(self):
        """Test push with SSH key authentication."""
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            def create_mock_response(data):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json = MagicMock(return_value=data)
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            
            mock_client.post.side_effect = [
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({
                    "url": "https://github.com/org/repo/pull/1",
                    "number": 1
                })
            ]
            
            result = await push_test_to_git(
                test_case_id="test123",
                test_title="Test",
                script_content="await page.goto('/');",
                provider="github",
                repo_url="git@github.com:org/repo.git",
                ssh_key_name="my-ssh-key"
            )
            
            assert result["success"] is True
            
            # Verify SSH key was passed in requests
            clone_call = mock_client.post.call_args_list[0]
            assert "ssh_key_name" in clone_call[1]["json"]
            assert clone_call[1]["json"]["ssh_key_name"] == "my-ssh-key"
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_sanitizes_filename(self):
        """Test that test title is sanitized for filename."""
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            def create_mock_response(data):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json = MagicMock(return_value=data)
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            
            mock_client.post.side_effect = [
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({
                    "url": "https://github.com/org/repo/pull/1",
                    "number": 1
                })
            ]
            
            # Title with special characters
            result = await push_test_to_git(
                test_case_id="test123",
                test_title="User's Login/Logout @Test #1",
                script_content="await page.goto('/');",
                provider="github",
                repo_url="https://github.com/org/repo.git"
            )
            
            # Filename should not contain special characters
            file_path = result["file_path"]
            assert "/" in file_path  # Directory separator OK
            assert "@" not in file_path.split('/')[-1]  # No @ in filename
            assert "#" not in file_path.split('/')[-1]  # No # in filename
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_handles_existing_repo(self):
        """Test that push handles existing repository (pull instead of clone)."""
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            def create_mock_response(data):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json = MagicMock(return_value=data)
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            
            # First call (pull) succeeds - repo exists
            mock_client.post.side_effect = [
                create_mock_response({"success": True}),  # pull
                create_mock_response({"success": True}),  # branch
                create_mock_response({"success": True}),  # write
                create_mock_response({"success": True}),  # commit
                create_mock_response({"success": True}),  # push
                create_mock_response({
                    "url": "https://github.com/org/repo/pull/1",
                    "number": 1
                })  # PR
            ]
            
            result = await push_test_to_git(
                test_case_id="test123",
                test_title="Test",
                script_content="await page.goto('/');",
                provider="github",
                repo_url="https://github.com/org/repo.git"
            )
            
            assert result["success"] is True
            assert result["cloned"] is False  # Repo was pulled, not cloned
    
    @pytest.mark.asyncio
    async def test_push_test_to_git_branch_naming(self):
        """Test that branch names follow expected pattern."""
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            def create_mock_response(data):
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json = MagicMock(return_value=data)
                mock_resp.raise_for_status = MagicMock()
                return mock_resp
            
            mock_client.post.side_effect = [
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({"success": True}),
                create_mock_response({
                    "url": "https://github.com/org/repo/pull/1",
                    "number": 1
                })
            ]
            
            result = await push_test_to_git(
                test_case_id="abc123xyz",
                test_title="Test",
                script_content="await page.goto('/');",
                provider="github",
                repo_url="https://github.com/org/repo.git"
            )
            
            branch_name = result["branch_name"]
            assert branch_name.startswith("feat/test-")
            assert "abc123xyz" in branch_name
            # Should have timestamp (format: feat/test-{id}-{timestamp})
            assert len(branch_name.split('-')) >= 3


class TestGitIntegrationEdgeCases:
    """Tests for edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_push_test_handles_git_service_error(self):
        """Test that push handles git service errors gracefully."""
        with patch('git_integration.httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Clone fails - mock the async post call properly
            async def raise_error(*args, **kwargs):
                mock_response = MagicMock()
                mock_response.status_code = 500
                raise httpx.HTTPStatusError(
                    "Internal Server Error",
                    request=MagicMock(),
                    response=mock_response
                )
            
            mock_client.post.side_effect = raise_error

            with pytest.raises(httpx.HTTPStatusError):
                await push_test_to_git(
                    test_case_id="test123",
                    test_title="Test",
                    script_content="await page.goto('/');",
                    provider="github",
                    repo_url="https://github.com/org/repo.git"
                )
    
    @pytest.mark.asyncio
    async def test_generate_test_file_handles_long_title(self):
        """Test that long titles are handled properly."""
        title = "A" * 200  # Very long title
        script_content = "await page.goto('/');"
        test_id = "long123"
        
        result = generate_playwright_test_file(title, script_content, test_id)
        
        # Should still generate valid file
        assert "import { test, expect } from '@playwright/test';" in result
        assert "test.describe(" in result
    
    @pytest.mark.asyncio
    async def test_push_test_with_different_providers(self):
        """Test push works with different git providers."""
        for provider in ["github", "gitlab", "azure"]:
            with patch('git_integration.httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                def create_mock_response(data):
                    mock_resp = MagicMock()
                    mock_resp.status_code = 200
                    mock_resp.json = MagicMock(return_value=data)
                    mock_resp.raise_for_status = MagicMock()
                    return mock_resp
                
                mock_client.post.side_effect = [
                    create_mock_response({"success": True}),
                    create_mock_response({"success": True}),
                    create_mock_response({"success": True}),
                    create_mock_response({"success": True}),
                    create_mock_response({"success": True}),
                    create_mock_response({
                        "url": f"https://{provider}.com/org/repo/pull/1",
                        "number": 1
                    })
                ]
                
                result = await push_test_to_git(
                    test_case_id="test123",
                    test_title="Test",
                    script_content="await page.goto('/');",
                    provider=provider,
                    repo_url=f"https://{provider}.com/org/repo.git"
                )
                
                assert result["success"] is True
                assert provider in result["pr_url"]
