"""Unit tests for concept resolver service."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.concept_resolver import resolve_concept, suggest_concepts


class MockCursor:
    """Mock async cursor that supports to_list, limit, and async iteration."""

    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs
        self._index = 0

    def limit(self, n: int) -> "MockCursor":
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length: int) -> list[dict]:
        return self._docs[:length]

    def __aiter__(self) -> "MockCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict:
        if self._index >= len(self._docs):
            raise StopAsyncIteration
        doc = self._docs[self._index]
        self._index += 1
        return doc


def make_mock_collection(
    find_one_result: dict | None = None,
    find_results: list[dict] | None = None,
    aggregate_results: list[dict] | None = None,
) -> AsyncMock:
    """Create a mock AsyncIOMotorCollection."""
    col = AsyncMock()
    col.find_one = AsyncMock(return_value=find_one_result)
    col.find = MagicMock(return_value=MockCursor(find_results or []))
    col.aggregate = MagicMock(return_value=MockCursor(aggregate_results or []))
    return col


@pytest.mark.asyncio
async def test_translation_hub_resolution() -> None:
    """When English entry has enough translations, use translation hub strategy only."""
    translations = [{"word": f"word{i}", "lang": f"Lang{i}"} for i in range(12)]
    hub_doc = {
        "word": "fire",
        "lang": "English",
        "translations": translations,
    }
    found_docs = [
        {"word": f"word{i}", "lang": f"Lang{i}", "phonetic": {"ipa": f"ipa{i}"}} for i in range(12)
    ]

    col = make_mock_collection(find_one_result=hub_doc, find_results=found_docs)

    results, method = await resolve_concept(col, "fire")
    assert method == "translation_hub"
    assert len(results) == 12


@pytest.mark.asyncio
async def test_gloss_fallback_when_no_hub() -> None:
    """When no translation hub exists, fall back to gloss search."""
    gloss_docs = [
        {"word": "xyz", "lang": "SomeLang", "phonetic": {"ipa": "test"}},
    ]

    col = make_mock_collection(find_one_result=None, find_results=gloss_docs)

    _results, method = await resolve_concept(col, "obscure_concept")
    assert method == "gloss_search"


@pytest.mark.asyncio
async def test_combined_when_hub_sparse() -> None:
    """When hub produces < 10 results, also uses gloss search."""
    hub_doc = {
        "word": "rare",
        "lang": "English",
        "translations": [{"word": "raro", "lang": "Spanish"}],
    }
    hub_results = [
        {"word": "raro", "lang": "Spanish", "phonetic": {"ipa": "ɾaɾo"}},
    ]
    # Gloss fallback docs
    gloss_docs = [
        {"word": "sjelden", "lang": "Norwegian", "phonetic": {"ipa": "ʂɛldn"}},
    ]

    col = AsyncMock()
    col.find_one = AsyncMock(return_value=hub_doc)

    call_count = 0

    def mock_find(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MockCursor(hub_results)
        return MockCursor(gloss_docs)

    col.find = MagicMock(side_effect=mock_find)

    results, method = await resolve_concept(col, "rare")
    assert method == "combined"
    assert len(results) == 2


@pytest.mark.asyncio
async def test_suggest_concepts() -> None:
    """Suggestion endpoint returns concepts with translation counts."""
    agg_results = [
        {"concept": "fire", "translation_count": 342, "pos": "noun"},
        {"concept": "fish", "translation_count": 280, "pos": "noun"},
    ]

    col = make_mock_collection(aggregate_results=agg_results)

    suggestions = await suggest_concepts(col, "fi", limit=10)
    assert len(suggestions) == 2
    assert suggestions[0]["concept"] == "fire"
    assert suggestions[0]["translation_count"] == 342
