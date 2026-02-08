"""Resolve a concept (e.g. "fire") to words across all languages.

Uses Wiktionary translation hubs as the primary strategy,
with gloss search as fallback.
"""

import re

from motor.motor_asyncio import AsyncIOMotorCollection

_WORD_PROJECTION = {
    "_id": 0,
    "word": 1,
    "lang": 1,
    "lang_code": 1,
    "pos": 1,
    "phonetic": 1,
    "etymology_text": 1,
    "etymology_templates": 1,
    "senses": {"$slice": 1},
}


async def resolve_concept(
    col: AsyncIOMotorCollection,
    concept: str,
    pos: str | None = None,
    max_words: int = 200,
) -> tuple[list[dict], str]:
    """Find all words across languages that express the given concept.

    Strategy A: Translation hub -- extract translations from the English entry.
    Strategy B: Gloss search -- search senses.glosses for exact match (fallback).

    Returns (list of word documents, resolution_method string).
    """
    results, method = await _resolve_via_hub(col, concept, pos, max_words)

    # Strategy B: Gloss search fallback (when < 10 results from hub)
    if len(results) < 10:
        method = "gloss_search" if not method else "combined"
        results = await _augment_via_gloss(col, concept, pos, max_words, results)

    return results, method


async def _resolve_via_hub(
    col: AsyncIOMotorCollection,
    concept: str,
    pos: str | None,
    max_words: int,
) -> tuple[list[dict], str]:
    """Strategy A: resolve concept via Wiktionary translation hub."""
    hub = await col.find_one(
        {
            "word": concept,
            "lang": "English",
            "translations": {"$exists": True, "$ne": []},
        },
        {"translations": 1, "senses": 1, "word": 1, "lang": 1},
    )

    if not hub or not hub.get("translations"):
        return [], ""

    seen: set[tuple[str, str]] = set()
    lookup_pairs = []

    for t in hub["translations"]:
        word = t.get("word", "")
        lang = t.get("lang", "")
        if word and lang and (word, lang) not in seen:
            seen.add((word, lang))
            lookup_pairs.append({"word": word, "lang": lang})

    if (concept, "English") not in seen:
        lookup_pairs.append({"word": concept, "lang": "English"})

    if not lookup_pairs:
        return [], "translation_hub"

    query: dict = {
        "$or": lookup_pairs,
        "phonetic.ipa": {"$exists": True, "$ne": None},
    }
    if pos:
        query["pos"] = pos

    cursor = col.find(query, _WORD_PROJECTION).limit(max_words + 50)
    seen: set[tuple[str, str]] = set()
    results: list[dict] = []
    async for doc in cursor:
        key = (doc["word"], doc["lang"])
        if key not in seen:
            seen.add(key)
            results.append(doc)
            if len(results) >= max_words:
                break
    return results, "translation_hub"


async def _augment_via_gloss(
    col: AsyncIOMotorCollection,
    concept: str,
    pos: str | None,
    max_words: int,
    existing: list[dict],
) -> list[dict]:
    """Strategy B: augment results via gloss search."""
    escaped_concept = re.escape(concept)
    query: dict = {
        "senses.glosses": {"$regex": f"^{escaped_concept}$", "$options": "i"},
        "phonetic.ipa": {"$exists": True, "$ne": None},
    }
    if pos:
        query["pos"] = pos

    existing_keys = {(r["word"], r["lang"]) for r in existing}
    remaining = max_words - len(existing)

    cursor = col.find(query, _WORD_PROJECTION).limit(remaining + 50)
    async for doc in cursor:
        key = (doc["word"], doc["lang"])
        if key not in existing_keys:
            existing.append(doc)
            existing_keys.add(key)
            if len(existing) >= max_words:
                break

    return existing


async def suggest_concepts(col: AsyncIOMotorCollection, query: str, limit: int = 10) -> list[dict]:
    """Suggest concepts that have translation hubs, matching a prefix query."""
    escaped = re.escape(query)
    pipeline = [
        {
            "$match": {
                "word": {"$regex": f"^{escaped}", "$options": "i"},
                "lang": "English",
                "translations": {"$exists": True, "$not": {"$size": 0}},
            }
        },
        {
            "$project": {
                "concept": "$word",
                "pos": "$pos",
                "translation_count": {"$size": "$translations"},
            }
        },
        {"$sort": {"translation_count": -1}},
        {"$limit": limit},
    ]
    results = []
    async for doc in col.aggregate(pipeline):
        results.append(
            {
                "concept": doc["concept"],
                "translation_count": doc["translation_count"],
                "pos": doc.get("pos", ""),
            }
        )
    return results
