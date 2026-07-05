"""Pytest configuration and fixtures."""

from typing import Any

import pytest
from app.services import concept_resolver, lang_cache


@pytest.fixture(autouse=True)
def _reset_module_caches():
    """lang_cache and concept_resolver._concept_cache are module-global caches by
    explicit design (SPC-00020); reset both around every test so no test depends
    on load order or a prior test's state."""
    lang_cache._code_to_name.clear()
    lang_cache._name_to_code.clear()
    concept_resolver._concept_cache.clear()
    yield
    lang_cache._code_to_name.clear()
    lang_cache._name_to_code.clear()
    concept_resolver._concept_cache.clear()


@pytest.fixture
async def test_db() -> None:
    """Provide test database connection.

    TODO: Implement test database fixture with isolated test data.
    This should create a separate test database to avoid interfering
    with the main etymology database.

    Returns:
        AsyncIOMotorCollection: Test database collection
    """
    # Placeholder implementation
    # In the future, this should:
    # 1. Connect to a test database (e.g., etymology_test)
    # 2. Load fixture data
    # 3. Yield the collection
    # 4. Clean up after tests


@pytest.fixture
def sample_etymology_doc() -> dict[str, Any]:
    """Provide sample etymology document for testing.

    Returns:
        dict: Sample Kaikki document with etymology templates
    """
    return {
        "word": "cheese",
        "lang": "English",
        "lang_code": "en",
        "etymology_templates": [
            {
                "name": "inh",
                "args": {
                    "1": "en",
                    "2": "enm",
                    "3": "chese",
                },
            },
            {
                "name": "inh",
                "args": {
                    "1": "enm",
                    "2": "ang",
                    "3": "ċīese",
                },
            },
        ],
        "etymology_text": "From Middle English chese, from Old English ċīese.",
    }
