# Releases Service Tests

Comprehensive test suite for the Releases Management Service.

## Test Structure

```
tests/
├── __init__.py                 # Package marker
├── conftest.py                 # Shared fixtures and configuration
├── test_health.py              # Health check endpoint tests
├── test_create_release.py      # Release creation tests
├── test_get_release.py         # Individual release retrieval tests
├── test_list_releases.py       # Release listing and search tests
├── test_update_release.py      # Release update tests
├── test_delete_release.py      # Release deletion tests
└── test_edge_cases.py          # Edge cases and error conditions
```

## Running Tests

### Install Dependencies

```bash
cd services/releases
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_create_release.py
```

### Run Specific Test

```bash
pytest tests/test_create_release.py::test_create_release_minimal
```

### Run with Coverage

```bash
pytest --cov=. --cov-report=html
```

View coverage report: `htmlcov/index.html`

### Run with Verbose Output

```bash
pytest -v
```

### Run Only Fast Tests

```bash
pytest -m "not slow"
```

## Test Coverage

Current test coverage includes:

### Health Endpoint
- ✅ Health check returns 200 OK

### Create Release (17 tests)
- ✅ Create with minimal fields
- ✅ Create with all fields
- ✅ Create with empty lists
- ✅ Validation error for missing name
- ✅ Special characters in name/description
- ✅ Multiple releases creation
- ✅ Timestamps automatically set

### Get Release (5 tests)
- ✅ Get by valid ID
- ✅ 404 for non-existent release
- ✅ 400 for invalid ID format
- ✅ All fields returned
- ✅ Edge cases

### List Releases (14 tests)
- ✅ List empty collection
- ✅ List all releases
- ✅ Sorted by updated_at descending
- ✅ Pagination (skip/limit)
- ✅ Search by name
- ✅ Search by description
- ✅ Case-insensitive search
- ✅ Partial match search
- ✅ No results for invalid search
- ✅ Input validation

### Update Release (14 tests)
- ✅ Update individual fields
- ✅ Update multiple fields
- ✅ 404 for non-existent release
- ✅ 400 for invalid ID
- ✅ 400 for empty payload
- ✅ Null values ignored
- ✅ updated_at timestamp changed
- ✅ created_at preserved
- ✅ Clear arrays

### Delete Release (7 tests)
- ✅ Delete existing release
- ✅ 404 for non-existent release
- ✅ 400 for invalid ID
- ✅ Delete twice returns 404
- ✅ Other releases unaffected
- ✅ Delete all releases
- ✅ Recreate after deletion

### Edge Cases (11 tests)
- ✅ Very long name/description
- ✅ Unicode characters
- ✅ HTML in fields
- ✅ Large ID arrays
- ✅ Regex special characters in search
- ✅ Concurrent updates
- ✅ Duplicate IDs in arrays
- ✅ Idempotent updates
- ✅ Malformed JSON
- ✅ Missing content type

**Total: 68 tests** covering all CRUD operations, validation, error handling, and edge cases.

## Test Database

Tests use a separate test database (`ai_testing_test`) to avoid affecting production data.

Configuration in `conftest.py`:
```python
os.environ["MONGO_DB_NAME"] = "ai_testing_test"
```

The database is cleaned before and after each test to ensure isolation.

## Fixtures

### `db`
Provides a clean MongoDB database instance for each test.

### `client`
Provides an async HTTP client for making API requests.

### `sample_release`
Creates a single release with all fields populated.

### `multiple_releases`
Creates 3 releases with different data for list/search testing.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Releases Service

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      mongodb:
        image: mongo:8.0
        ports:
          - 27017:27017
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd services/releases
          pip install -r requirements-test.txt
      
      - name: Run tests
        run: |
          cd services/releases
          pytest --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Writing New Tests

### Test Naming Convention

- Test files: `test_<feature>.py`
- Test functions: `test_<behavior>`
- Use descriptive names that explain what is being tested

### Example Test

```python
@pytest.mark.asyncio
async def test_create_release_with_dates(client):
    """Test creating a release with from_date and to_date."""
    payload = {
        "name": "Q1 Release",
        "from_date": "2025-01-01T00:00:00Z",
        "to_date": "2025-03-31T23:59:59Z"
    }
    
    response = await client.post("/releases", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["from_date"] == "2025-01-01T00:00:00Z"
```

### Best Practices

1. **One assertion per test** (when possible)
2. **Arrange-Act-Assert** pattern
3. **Descriptive docstrings**
4. **Use fixtures** for common setup
5. **Clean up** after tests
6. **Test error cases** as well as success
7. **Use meaningful test data**

## Troubleshooting

### MongoDB Connection Error

```bash
# Make sure MongoDB is running
docker-compose up -d mongodb
```

Or set test MongoDB URI:
```bash
export MONGO_TEST_URI="mongodb://localhost:27017"
```

### Tests Hang

Asyncio tests may hang if event loop is not properly configured. Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` is set in `pytest.ini`.

### Import Errors

Make sure you're in the releases service directory:
```bash
cd services/releases
PYTHONPATH=../.. pytest
```

## Future Improvements

- [ ] Add performance/load tests
- [ ] Add contract tests
- [ ] Mock external dependencies
- [ ] Add mutation testing
- [ ] Integration tests with other services
- [ ] Test database indexes and query performance
