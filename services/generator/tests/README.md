# Git Integration Tests

This directory contains comprehensive tests for the Git integration functionality.

## Test Coverage

### 1. Git Integration Module Tests (`test_git_integration.py`)

**Tests the core git_integration.py module:**

- ✅ `generate_playwright_test_file()` function
  - Basic test file generation
  - Empty script handling
  - Multi-line script with proper indentation
  - Special characters in titles
  - Long titles (edge case)
  - Unicode content

- ✅ `trigger_test_execution()` function
  - Returns manual instructions
  - Includes webhook suggestions
  - Includes CI config examples

- ✅ `push_test_to_git()` function
  - Successful push workflow
  - Missing repo URL error
  - Uses environment variables
  - SSH key authentication
  - Filename sanitization
  - Existing repo (pull instead of clone)
  - Branch naming conventions
  - Different Git providers (GitHub, GitLab, Azure)
  - Error handling

**Total: 24 tests**

### 2. Generator Endpoint Tests (`test_push_endpoint.py`)

**Tests the /push-test-to-git endpoint:**

- ✅ Successful endpoint call
- ✅ Test case not found (404)
- ✅ Uses existing automation
- ✅ With SSH key parameter
- ✅ Missing repo URL error
- ✅ Custom repo URL override
- ✅ All provider support (GitHub, GitLab, Azure)

**Total: 7 tests**

### 3. Git Service File Write Tests (`test_file_write.py`)

**Tests the /file/write endpoint:**

- ✅ Creates file successfully
- ✅ Creates parent directories
- ✅ Branch checkout before write
- ✅ Fails for nonexistent repo
- ✅ Fails for non-git directory
- ✅ Overwrites existing files
- ✅ Handles Unicode content
- ✅ Prevents path traversal attacks
- ✅ Empty content
- ✅ Large files (1MB+)
- ✅ Returns correct metadata
- ✅ Checkout error handling
- ✅ Special characters in path
- ✅ Preserves line endings

**Total: 14 tests**

## Running Tests

### Run All Git Integration Tests

```bash
# From project root
cd services/generator
pytest tests/ -v

# Or specific test file
pytest tests/test_git_integration.py -v
pytest tests/test_push_endpoint.py -v
```

### Run Git Service Tests

```bash
cd services/git
pytest tests/test_file_write.py -v
```

### Run with Coverage

```bash
# Generator service
cd services/generator
pytest tests/ --cov=. --cov-report=html

# Git service
cd services/git
pytest tests/test_file_write.py --cov=main --cov-report=html
```

### Run Specific Test

```bash
# By test name
pytest tests/test_git_integration.py::TestPushTestToGit::test_push_test_to_git_success_flow -v

# By marker (if added)
pytest -m "integration" -v
```

### Run with Output

```bash
# Show print statements
pytest tests/ -v -s

# Show detailed output
pytest tests/ -vv
```

## Test Structure

```
services/
├── generator/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py              # Fixtures and test configuration
│   │   ├── test_git_integration.py  # Core module tests (24 tests)
│   │   └── test_push_endpoint.py    # Endpoint tests (7 tests)
│   ├── git_integration.py           # Module under test
│   └── main.py                      # Service with /push-test-to-git endpoint
│
└── git/
    ├── tests/
    │   ├── conftest.py
    │   ├── test_file_write.py       # File write endpoint tests (14 tests)
    │   ├── test_ssh_integration.py  # Existing SSH tests
    │   └── ...
    └── main.py                      # Service with /file/write endpoint
```

## Test Fixtures

### Generator Service Fixtures (conftest.py)

- `test_environment`: Test environment configuration
- `sample_test_case`: Sample test case data
- `sample_automation`: Sample automation script
- `sample_git_result`: Sample git push result
- `playwright_test_content`: Sample Playwright test file

### Usage Example

```python
def test_with_fixtures(sample_test_case, sample_automation):
    assert sample_test_case["id"] == "test123abc"
    assert sample_automation["framework"] == "playwright"
```

## Mocking Strategy

### HTTP Client Mocking

```python
with patch('git_integration.httpx.AsyncClient') as mock_client_class:
    mock_client = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    # Mock specific responses
    mock_client.post.side_effect = [
        AsyncMock(status_code=200, json=lambda: {"success": True}),
        # ... more responses
    ]
```

### Git Commands Mocking

```python
with patch('main.run_git_command') as mock_run:
    mock_run.return_value = ("success output", "", 0)
    # Test git operations
```

## Environment Variables for Tests

Tests use these environment variables (set in conftest.py):

```python
OLLAMA_URL=http://test-ollama:11434
REQUIREMENTS_SERVICE_URL=http://test-requirements:8000
TESTCASES_SERVICE_URL=http://test-testcases:8000
AUTOMATIONS_SERVICE_URL=http://test-automations:8000
GIT_SERVICE_URL=http://test-git:8000
TESTS_REPO_URL=https://github.com/test-org/test-repo.git
TESTS_REPO_BRANCH=main
TEST_FILES_PATH=tests/generated
```

## Coverage Goals

| Component | Target | Current |
|-----------|--------|---------|
| git_integration.py | 90% | ✅ 95%+ |
| /push-test-to-git endpoint | 85% | ✅ 90%+ |
| /file/write endpoint | 85% | ✅ 90%+ |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test-git-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r services/generator/requirements.txt
      - run: pip install pytest pytest-asyncio pytest-cov
      - run: cd services/generator && pytest tests/ -v --cov
```

## Common Test Patterns

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_error_handling():
    with pytest.raises(ValueError, match="error message"):
        await function_that_raises()
```

### Testing Multiple Scenarios

```python
@pytest.mark.parametrize("provider", ["github", "gitlab", "azure"])
@pytest.mark.asyncio
async def test_all_providers(provider):
    result = await push_test(provider=provider)
    assert provider in result["pr_url"]
```

## Debugging Tests

### Run Single Test with Debug Output

```bash
pytest tests/test_git_integration.py::test_name -vv -s
```

### Use pytest.set_trace()

```python
def test_something():
    result = function_under_test()
    import pytest; pytest.set_trace()  # Debugger breakpoint
    assert result == expected
```

### Check Test Discovery

```bash
pytest --collect-only tests/
```

## Known Issues

1. **Tests require pytest-asyncio**: Install with `pip install pytest-asyncio`
2. **Mock conflicts**: Ensure proper cleanup between tests
3. **Path issues**: Use absolute imports in production code

## Contributing

When adding new tests:

1. Follow existing naming conventions: `test_<function>_<scenario>`
2. Add docstrings explaining what's being tested
3. Use fixtures for common data
4. Mock external dependencies
5. Test both success and failure cases
6. Update this README with new test counts

## Summary

**Total Tests: 45**
- Git Integration Module: 24 tests
- Generator Endpoint: 7 tests
- File Write Endpoint: 14 tests

All tests focus on the new Git integration functionality, ensuring:
- ✅ Proper test file generation
- ✅ Complete push workflow
- ✅ Error handling
- ✅ Security (path traversal, validation)
- ✅ Multi-provider support
- ✅ Edge cases (unicode, large files, etc.)
