# Quick Test Commands

## Run All Tests

```bash
# Generator service tests (31 tests)
cd services/generator && pytest tests/ -v

# Git service file write tests (14 tests)
cd services/git && pytest tests/test_file_write.py -v
```

## Run Specific Test Files

```bash
# Git integration module (24 tests)
pytest tests/test_git_integration.py -v

# Push endpoint (7 tests)
pytest tests/test_push_endpoint.py -v

# File write endpoint (14 tests)
pytest tests/test_file_write.py -v
```

## Run with Coverage

```bash
# With HTML report
pytest tests/ --cov=. --cov-report=html

# View report
open htmlcov/index.html  # macOS/Linux
start htmlcov/index.html  # Windows
```

## Run Single Test

```bash
pytest tests/test_git_integration.py::TestPushTestToGit::test_push_test_to_git_success_flow -v
```

## Debug Mode

```bash
# Show print statements
pytest tests/ -v -s

# Very verbose
pytest tests/ -vv

# Stop on first failure
pytest tests/ -x
```

## Quick Health Check

```bash
# Just verify tests are discovered
pytest --collect-only tests/

# Run fastest tests first
pytest tests/ -v --durations=0
```

## Expected Output

```
tests/test_git_integration.py::TestGeneratePlaywrightTestFile::test_generate_basic_test_file PASSED
tests/test_git_integration.py::TestPushTestToGit::test_push_test_to_git_success_flow PASSED
...

======================== 45 passed in 5.50s ========================
```

✅ All 45 tests should pass!
