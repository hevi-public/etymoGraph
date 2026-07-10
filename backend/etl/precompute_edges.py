"""Precompute compound/affix etymology edges for all entries.

Standalone batch script using sync pymongo.
Run outside Docker against localhost:27017.

Scans all documents with compound/affix templates, extracts component
relationships, validates component existence in the words collection,
and stores edges in the etymology_edges collection.

Usage:
    pip install pymongo
    python -m etl.precompute_edges
    python -m etl.precompute_edges --reprocess  # Drop and rebuild from scratch
"""

import os
import sys
import time
from functools import lru_cache

from app.services.etymology_classifier import AFFIX_TEMPLATES
from app.services.template_parser import normalize_word
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/etymology")
BATCH_SIZE = 5000


def load_lang_lookup(db) -> dict[str, str]:
    """Build lang_code -> lang_name mapping from languages collection."""
    lookup = {}
    for doc in db.languages.find({}, {"_id": 0, "lang_code": 1, "lang": 1}):
        code = doc.get("lang_code", "")
        name = doc.get("lang", "")
        if code and name:
            lookup[code] = name
    return lookup


def make_word_checker(col):
    """Create a cached function that checks if a word exists in the words collection."""

    @lru_cache(maxsize=200_000)
    def word_exists(word: str, lang: str) -> bool:
        """Check if a word exists, falling back to normalized form."""
        if col.find_one({"word": word, "lang": lang}, {"_id": 1}):
            return True
        normalized = normalize_word(word)
        if normalized != word:
            return bool(col.find_one({"word": normalized, "lang": lang}, {"_id": 1}))
        return False

    return word_exists


def extract_compound_edges(doc: dict, lang_lookup: dict[str, str]) -> list[dict]:
    """Extract compound/affix component edges from a single document.

    Returns list of edge dicts ready for insertion into etymology_edges.
    """
    word = doc.get("word", "")
    lang = doc.get("lang", "")
    lang_code = doc.get("lang_code", "")
    if not word or not lang:
        return []

    edges = []
    seen = set()

    for tmpl in doc.get("etymology_templates", []):
        name = tmpl.get("name", "")
        if name not in AFFIX_TEMPLATES:
            continue

        args = tmpl.get("args", {})
        comp_lang_code = args.get("1", "")
        if not comp_lang_code:
            continue

        comp_lang = lang_lookup.get(comp_lang_code, "")
        if not comp_lang:
            continue

        # Extract component words from args 2-5
        for key in ["2", "3", "4", "5"]:
            comp_word = args.get(key, "")
            if not comp_word:
                continue
            # Skip affixes (starting with - or ending with -)
            if comp_word.startswith("-") or comp_word.endswith("-"):
                continue

            dedup_key = (comp_word, comp_lang_code)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            edges.append(
                {
                    "from_word": comp_word,
                    "from_lang": comp_lang,
                    "from_lang_code": comp_lang_code,
                    "to_word": word,
                    "to_lang": lang,
                    "to_lang_code": lang_code,
                    "edge_type": "component",
                    "source_template": name,
                }
            )

    return edges


def precompute(reprocess: bool = False) -> None:
    """Extract and store compound/affix edges in the etymology_edges collection."""
    client = MongoClient(MONGO_URI)
    db = client.etymology
    words_col = db.words
    edges_col = db.etymology_edges

    print("Loading language lookup...")
    lang_lookup = load_lang_lookup(db)
    print(f"  {len(lang_lookup)} language codes loaded.")

    if reprocess:
        print("Dropping existing etymology_edges collection...")
        edges_col.drop()

    # Check if collection already has data
    existing = edges_col.count_documents({})
    if existing > 0 and not reprocess:
        print(f"etymology_edges already has {existing:,} documents. Use --reprocess to rebuild.")
        return

    print("Querying documents with compound/affix templates...")
    query = {"etymology_templates.name": {"$in": list(AFFIX_TEMPLATES)}}
    total = words_col.count_documents(query)
    print(f"  {total:,} documents to process.")

    if total == 0:
        print("Nothing to process.")
        return

    # Create word existence checker with LRU cache
    word_exists = make_word_checker(words_col)

    cursor = words_col.find(
        query,
        {"_id": 0, "word": 1, "lang": 1, "lang_code": 1, "etymology_templates": 1},
    )

    bulk_edges: list[dict] = []
    processed = 0
    total_edges = 0
    edges_with_match = 0
    start = time.time()

    for doc in cursor:
        edges = extract_compound_edges(doc, lang_lookup)

        for edge in edges:
            # Check if the component word exists in the DB
            exists = word_exists(edge["from_word"], edge["from_lang"])
            edge["from_exists"] = exists
            if exists:
                edges_with_match += 1
            bulk_edges.append(edge)
            total_edges += 1

        processed += 1

        if len(bulk_edges) >= BATCH_SIZE:
            edges_col.insert_many(bulk_edges)
            bulk_edges = []
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            print(
                f"  {processed:,}/{total:,} docs ({processed / total * 100:.1f}%) "
                f"- {total_edges:,} edges - {rate:.0f} docs/sec"
            )

    if bulk_edges:
        edges_col.insert_many(bulk_edges)

    elapsed = time.time() - start

    print("\nCreating indexes...")
    edges_col.create_index([("to_word", 1), ("to_lang", 1)])
    edges_col.create_index([("from_word", 1), ("from_lang", 1)])

    print(
        f"\nDone in {elapsed:.1f}s. "
        f"Docs processed: {processed:,}, "
        f"Edges created: {total_edges:,}, "
        f"Components found in DB: {edges_with_match:,} "
        f"({edges_with_match / total_edges * 100:.1f}% match rate)"
        if total_edges > 0
        else f"\nDone in {elapsed:.1f}s. No edges created."
    )
    print(f"Word existence cache: {word_exists.cache_info()}")


if __name__ == "__main__":
    reprocess = "--reprocess" in sys.argv
    precompute(reprocess=reprocess)
