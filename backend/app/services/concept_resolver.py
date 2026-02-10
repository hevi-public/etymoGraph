"""Resolve a concept (e.g. "fire") to words across all languages.

Uses Wiktionary translation hubs as the primary strategy,
with gloss search as fallback.
"""

import re

from motor.motor_asyncio import AsyncIOMotorCollection

# In-memory cache for resolved concepts. Wiktionary data is static,
# so caching is safe for a single-user local tool.
_concept_cache: dict[tuple[str, str | None], tuple[list[dict], str]] = {}

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
) -> tuple[list[dict], str]:
    """Find all words across languages that express the given concept.

    Strategy A: Translation hub -- extract translations from the English entry.
    Strategy B: Gloss search -- search senses.glosses for exact match (fallback).

    Returns (list of word documents, resolution_method string).
    """
    cache_key = (concept.lower(), pos)
    if cache_key in _concept_cache:
        return _concept_cache[cache_key]

    results, method = await _resolve_via_hub(col, concept, pos)

    # Strategy B: Gloss search fallback (when < 10 results from hub)
    if len(results) < 10:
        method = "gloss_search" if not method else "combined"
        results = await _augment_via_gloss(col, concept, pos, results)

    _concept_cache[cache_key] = (results, method)
    return results, method


async def _resolve_via_hub(
    col: AsyncIOMotorCollection,
    concept: str,
    pos: str | None,
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

    cursor = col.find(query, _WORD_PROJECTION)
    seen: set[tuple[str, str]] = set()
    results: list[dict] = []
    async for doc in cursor:
        key = (doc["word"], doc["lang"])
        if key not in seen:
            seen.add(key)
            results.append(doc)
    return results, "translation_hub"


async def _augment_via_gloss(
    col: AsyncIOMotorCollection,
    concept: str,
    pos: str | None,
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

    cursor = col.find(query, _WORD_PROJECTION)
    async for doc in cursor:
        key = (doc["word"], doc["lang"])
        if key not in existing_keys:
            existing.append(doc)
            existing_keys.add(key)

    return existing


_SUGGEST_COLLATION = {"locale": "en", "strength": 2}


async def suggest_concepts(col: AsyncIOMotorCollection, query: str, limit: int = 10) -> list[dict]:
    """Suggest concepts that have translation hubs, matching a prefix query.

    Uses a range query with case-insensitive collation to leverage the
    lang_word_ci_translations index instead of scanning the full index with regex.
    """
    prefix = query.lower()
    # Build exclusive upper bound: "fire" -> "firs" + 1 = "firt" (conceptually)
    next_prefix = prefix[:-1] + chr(ord(prefix[-1]) + 1)

    pipeline = [
        {
            "$match": {
                "lang": "English",
                "word": {"$gte": prefix, "$lt": next_prefix},
                "translations.0": {"$exists": True},
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
    async for doc in col.aggregate(pipeline, collation=_SUGGEST_COLLATION):
        results.append(
            {
                "concept": doc["concept"],
                "translation_count": doc["translation_count"],
                "pos": doc.get("pos", ""),
            }
        )
    return results
