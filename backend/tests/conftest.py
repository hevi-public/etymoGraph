"""Pytest configuration and fixtures."""

from typing import Any

import pytest


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
