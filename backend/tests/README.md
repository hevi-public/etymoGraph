# Etymology Explorer Tests

## Test Structure

This directory contains unit tests for the Etymology Explorer backend services and utilities.

## Running Tests

```bash
# From project root
make test

# Or directly with pytest
cd backend
pytest

# Run specific test file
cd backend
pytest tests/test_etymology_classifier.py

# Run with verbose output
cd backend
pytest -v
```

## Test Files

### `conftest.py`
Pytest configuration and fixtures:
- `test_db()`: Test database fixture (TODO: implement with isolated test data)
- `sample_etymology_doc()`: Sample Kaikki document for testing

### `test_etymology_classifier.py`
Tests for etymology uncertainty detection and word mention extraction:
- Uncertainty detection from templates (`unk`, `unc`)
- Uncertainty detection from text patterns
- Word mention extraction from templates
- Priority handling (template > text)
- Edge cases (exclusion of ancestry words, affix filtering)

**Status**: ✅ Complete with full coverage

### `test_tree_builder.py`
Tests for TreeBuilder service:
- Basic word expansion and ancestry tracing
- Descendant discovery
- Cognate expansion
- Node/edge deduplication

**Status**: ⚠️ Partial - basic tests implemented, async tests require test database fixture

## Test Coverage

**Current coverage**:
- ✅ `etymology_classifier.py`: Full coverage (~15 tests)
- ⚠️ `tree_builder.py`: Basic unit tests for add_node/add_edge/result, integration tests TODO
- ❌ `template_parser.py`: Not yet covered
- ❌ `lang_cache.py`: Not yet covered

**Target coverage**:
- All services layer functions (business logic)
- All utility functions with complex logic
- Routers: basic happy path only (FastAPI handles validation)

## Test Database

**TODO**: Implement test database fixture for integration tests.

**Requirements**:
1. Separate MongoDB database (`etymology_test`)
2. Fixture data with known etymology chains
3. Setup/teardown for test isolation

**Example fixture data needed**:
- Simple ancestry chain (e.g., cheese → chese → ċīese)
- Word with descendants (e.g., PIE root → multiple languages)
- Word with cognates
- Word with uncertain etymology (unk/unc templates)

## Writing New Tests

Follow these conventions:

**Test naming**:
```python
def test_<function_name>_<scenario>():
    """Test <what is being tested> when <condition>."""
```

**Test structure** (Arrange-Act-Assert):
```python
def test_example():
    """Test example function with valid input."""
    # Arrange - set up test data
    input_data = {"key": "value"}

    # Act - call function under test
    result = function_under_test(input_data)

    # Assert - verify results
    assert result["key"] == "expected"
```

**Async tests**:
```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function_under_test()
    assert result is not None
```

## CI/CD Integration

**TODO**: Add GitHub Actions workflow to run tests on PR.

**Suggested workflow**:
1. Run `make lint` to check code style
2. Run `make test` to run all tests
3. Block merge if tests fail

## Additional Resources

- See `docs/CODING_STANDARDS.md` for testing standards
- Pytest documentation: https://docs.pytest.org/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
