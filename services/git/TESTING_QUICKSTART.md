# Quick Start: Git Service SSH Key Tests

Fast guide to run the SSH key management tests.

## Prerequisites

1. Python 3.11+
2. Git service dependencies installed

## Install & Run (5 minutes)

### 1. Install Test Dependencies

```bash
cd services/git
pip install pytest pytest-asyncio httpx
```

### 2. Run Tests

```bash
# All tests (should see 39 tests pass)
pytest tests/ -v

# Quick smoke test (just SSH key APIs)
pytest tests/test_ssh_keys.py -v

# With coverage report
pytest tests/ --cov=. --cov-report=term-missing
```

## Expected Output

```
tests/test_health.py::test_health_check PASSED
tests/test_ssh_keys.py::test_upload_ssh_key_success PASSED
tests/test_ssh_keys.py::test_upload_ssh_key_without_public_key PASSED
tests/test_ssh_keys.py::test_upload_ssh_key_invalid_name PASSED
tests/test_ssh_keys.py::test_upload_ssh_key_invalid_format PASSED
tests/test_ssh_keys.py::test_upload_ssh_key_duplicate PASSED
tests/test_ssh_keys.py::test_list_ssh_keys_empty PASSED
tests/test_ssh_keys.py::test_list_ssh_keys_multiple PASSED
tests/test_ssh_keys.py::test_get_ssh_key_details PASSED
tests/test_ssh_keys.py::test_get_ssh_key_not_found PASSED
tests/test_ssh_keys.py::test_delete_ssh_key PASSED
tests/test_ssh_keys.py::test_delete_ssh_key_with_public_key PASSED
tests/test_ssh_keys.py::test_delete_ssh_key_not_found PASSED
tests/test_ssh_manager.py::test_ssh_manager_initialization PASSED
tests/test_ssh_manager.py::test_add_key_success PASSED
tests/test_ssh_manager.py::test_add_key_with_public_key PASSED
tests/test_ssh_manager.py::test_add_key_invalid_name PASSED
tests/test_ssh_manager.py::test_add_key_invalid_format PASSED
tests/test_ssh_manager.py::test_add_key_duplicate PASSED
tests/test_ssh_manager.py::test_list_keys_empty PASSED
tests/test_ssh_manager.py::test_list_keys_multiple PASSED
tests/test_ssh_manager.py::test_get_key_success PASSED
tests/test_ssh_manager.py::test_get_key_not_found PASSED
tests/test_ssh_manager.py::test_delete_key_success PASSED
tests/test_ssh_manager.py::test_delete_key_with_public_key PASSED
tests/test_ssh_manager.py::test_delete_key_not_found PASSED
tests/test_ssh_manager.py::test_get_ssh_command_args_no_key PASSED
tests/test_ssh_manager.py::test_get_ssh_command_args_with_key PASSED
tests/test_ssh_manager.py::test_get_ssh_command_args_key_not_found PASSED
tests/test_ssh_manager.py::test_configure_git_ssh_no_key PASSED
tests/test_ssh_manager.py::test_configure_git_ssh_with_key PASSED
tests/test_ssh_integration.py::test_clone_with_ssh_key PASSED
tests/test_ssh_integration.py::test_clone_with_nonexistent_ssh_key PASSED
tests/test_ssh_integration.py::test_push_with_ssh_key PASSED
tests/test_ssh_integration.py::test_pull_with_ssh_key PASSED
tests/test_ssh_integration.py::test_clone_without_ssh_key PASSED
tests/test_ssh_integration.py::test_ssh_url_validation PASSED
tests/test_ssh_integration.py::test_invalid_protocol_rejected PASSED

========================= 39 passed in X.XXs =========================
```

## Test Breakdown

- **API Tests** (13): SSH key upload, list, get, delete
- **Manager Tests** (17): SSHKeyManager class unit tests
- **Integration Tests** (8): Git operations with SSH keys
- **Health Tests** (1): Basic health check

## Troubleshooting

### Import Errors
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Missing ssh-keygen
Some tests require `ssh-keygen` command. Install Git if not present:
- **Windows**: Install Git for Windows
- **Linux**: `apt-get install openssh-client`
- **macOS**: Pre-installed

### Permission Issues (Windows)
Permission tests (0600/0644) may behave differently on Windows. Tests account for this.

## CI/CD Integration

```yaml
# .github/workflows/test-git-service.yml
name: Test Git Service
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd services/git
          pip install -r requirements.txt
          pip install -r tests/requirements.txt
      - name: Run tests
        run: |
          cd services/git
          pytest tests/ --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## What's Tested

✅ **Security**: Key validation, permissions (0600/0644)  
✅ **API**: All CRUD operations on SSH keys  
✅ **Integration**: Git clone/push/pull with SSH  
✅ **Error Handling**: 400, 404, 409 responses  
✅ **Edge Cases**: Invalid names, formats, duplicates  

## Next Steps

1. Run tests: `pytest tests/ -v`
2. Check coverage: `pytest tests/ --cov=.`
3. Read [tests/README.md](tests/README.md) for details
4. Write additional tests as needed

**Total Time**: ~2 seconds to run all 39 tests
