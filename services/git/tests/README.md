# Git Service Tests

Comprehensive test suite for the Git service, including SSH key management functionality.

## Test Structure

```
tests/
├── conftest.py              # Test configuration and fixtures
├── test_health.py           # Health endpoint tests
├── test_ssh_keys.py         # SSH key management API tests
├── test_ssh_manager.py      # SSHKeyManager class unit tests
├── test_ssh_integration.py  # Git operations with SSH integration tests
└── requirements.txt         # Test dependencies
```

## Test Coverage

### SSH Key Management (`test_ssh_keys.py`)
- ✅ Upload SSH key (with/without public key)
- ✅ Upload validation (invalid name, format, duplicates)
- ✅ List SSH keys (empty, multiple)
- ✅ Get SSH key details
- ✅ Delete SSH key (single, with public key)
- ✅ Error handling (404s, 400s, 409s)

### SSH Key Manager (`test_ssh_manager.py`)
- ✅ Manager initialization
- ✅ Add key (with permissions check)
- ✅ Add key validation
- ✅ List keys
- ✅ Get key details
- ✅ Delete key
- ✅ SSH command args generation
- ✅ Git SSH configuration

### SSH Integration (`test_ssh_integration.py`)
- ✅ Clone with SSH key
- ✅ Push with SSH key
- ✅ Pull with SSH key
- ✅ SSH URL validation
- ✅ Protocol validation

### Health Check (`test_health.py`)
- ✅ Basic health check endpoint

## Running Tests

### Install Test Dependencies

```bash
cd services/git
pip install -r tests/requirements.txt
```

### Run All Tests

```bash
pytest tests/
```

### Run with Coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

### Run Specific Test File

```bash
pytest tests/test_ssh_keys.py -v
```

### Run Specific Test

```bash
pytest tests/test_ssh_keys.py::test_upload_ssh_key_success -v
```

## Test Fixtures

### Common Fixtures (from `conftest.py`)

- `event_loop`: Async event loop for tests
- `workspace_dir`: Clean workspace directory for each test
- `ssh_keys_dir`: Clean SSH keys directory for each test
- `client`: Async HTTP client for API testing
- `ssh_manager`: SSHKeyManager instance
- `valid_private_key`: Valid test SSH private key
- `valid_public_key`: Valid test SSH public key
- `invalid_private_key`: Invalid SSH key for error testing

## Writing New Tests

### Example Test Structure

```python
@pytest.mark.asyncio
async def test_my_feature(client, valid_private_key):
    """Test description."""
    # Arrange
    payload = {
        "key_name": "test_key",
        "private_key": valid_private_key
    }
    
    # Act
    response = await client.post("/ssh-keys", json=payload)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["key_name"] == "test_key"
```

### Mocking Git Commands

For tests that don't actually execute Git commands:

```python
from unittest.mock import patch

@pytest.mark.asyncio
async def test_clone_operation(client):
    with patch("main.run_git_command") as mock_run:
        mock_run.return_value = ("Success", "", 0)
        
        response = await client.post("/clone", json={
            "repo_url": "https://github.com/user/repo.git"
        })
        
        assert response.status_code == 200
```

## Test Data

### Valid SSH Keys

The test fixtures include realistic (but non-functional) SSH key examples for testing:
- Private key in OpenSSH format
- Public key in authorized_keys format

These keys are **only for testing** and should never be used for real authentication.

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Git Service Tests
  run: |
    cd services/git
    pip install -r requirements.txt
    pip install -r tests/requirements.txt
    pytest tests/ --cov --cov-report=xml
```

## Troubleshooting

### Import Errors

If you see import errors, make sure you're in the correct directory:
```bash
cd services/git
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Permission Errors

Some tests check file permissions. On Windows, permission checks may behave differently. Tests account for this with platform-specific checks.

### Async Test Warnings

If you see warnings about async fixtures, ensure `pytest-asyncio` is installed:
```bash
pip install pytest-asyncio
```

## Coverage Goals

Target: **90%+ coverage** for SSH key management features

Current coverage areas:
- SSH key upload/validation
- SSH key storage/retrieval
- SSH key deletion
- Git operation integration
- Error handling
- Security (permissions, validation)
