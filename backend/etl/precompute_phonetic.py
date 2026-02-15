"""Precompute Dolgopolsky sound classes for all entries with IPA data.

Standalone batch script using sync pymongo + lingpy.
Runs inside Docker via `make precompute-phonetic`.

Usage:
    make precompute-phonetic          # Docker (default)
    MONGO_URI=mongodb://localhost:27017/etymology python -m etl.precompute_phonetic  # host
"""

import os
import re
import sys
import time

from lingpy import ipa2tokens, tokens2class
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017/etymology")
BATCH_SIZE = 5000


def extract_ipa(sounds: list[dict]) -> str | None:
    """Extract best IPA from a sounds array, preferring untagged entries."""
    if not sounds:
        return None
    for entry in sounds:
        if "ipa" in entry and "tags" not in entry:
            return _clean_ipa(entry["ipa"])
    for entry in sounds:
        if "ipa" in entry:
            return _clean_ipa(entry["ipa"])
    return None


def _clean_ipa(ipa_string: str) -> str:
    """Strip delimiters, stress marks, and syllable dots from IPA."""
    cleaned = re.sub(r"^[/\[]|[/\]]$", "", ipa_string.strip())
    cleaned = re.sub(r"[ˈˌ.]", "", cleaned)
    return cleaned


def get_sound_classes(ipa: str) -> dict | None:
    """Convert cleaned IPA to Dolgopolsky sound class representations.

    Returns dict with dolgo_classes, dolgo_consonants, dolgo_first2, tokens,
    or None on failure.
    """
    if not ipa:
        return None
    try:
        tokens = ipa2tokens(ipa)
        classes = tokens2class(tokens, "dolgo")
        class_string = "".join(classes)
        consonant_classes = "".join(c for c in classes if c not in ("V", "0", "_"))
        first_two = consonant_classes[:2] if len(consonant_classes) >= 2 else consonant_classes
        return {
            "tokens": tokens,
            "dolgo_classes": class_string,
            "dolgo_consonants": consonant_classes,
            "dolgo_first2": first_two,
        }
    except Exception as e:
        print(f"  Warning: Could not process IPA '{ipa}': {e}")
        return None


def precompute(reprocess: bool = False) -> None:
    """Enrich all entries that have sounds with a phonetic subdocument."""
    client = MongoClient(MONGO_URI)
    col = client.etymology.words

    print("Creating phonetic indexes...")
    col.create_index("phonetic.dolgo_first2")
    col.create_index("phonetic.dolgo_consonants")
    col.create_index([("phonetic.dolgo_first2", 1), ("lang", 1)])

    query: dict = {"sounds": {"$exists": True, "$ne": []}}
    if not reprocess:
        query["phonetic"] = {"$exists": False}

    total = col.count_documents(query)
    print(f"Processing {total:,} entries...")

    if total == 0:
        print("Nothing to process.")
        return

    cursor = col.find(query, {"_id": 1, "sounds": 1, "word": 1, "lang": 1})
    bulk_ops: list = []
    processed = 0
    enriched = 0
    no_ipa = 0
    errors = 0
    start = time.time()

    for doc in cursor:
        ipa = extract_ipa(doc.get("sounds", []))

        if not ipa:
            no_ipa += 1
            bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"phonetic": {"ipa": None}}}))
        else:
            sc = get_sound_classes(ipa)
            if sc:
                enriched += 1
                bulk_ops.append(
                    UpdateOne(
                        {"_id": doc["_id"]},
                        {
                            "$set": {
                                "phonetic": {
                                    "ipa": ipa,
                                    "dolgo_classes": sc["dolgo_classes"],
                                    "dolgo_consonants": sc["dolgo_consonants"],
                                    "dolgo_first2": sc["dolgo_first2"],
                                    "tokens": sc["tokens"],
                                }
                            }
                        },
                    )
                )
            else:
                errors += 1
                bulk_ops.append(
                    UpdateOne(
                        {"_id": doc["_id"]},
                        {"$set": {"phonetic": {"ipa": ipa, "error": True}}},
                    )
                )

        if len(bulk_ops) >= BATCH_SIZE:
            col.bulk_write(bulk_ops)
            processed += len(bulk_ops)
            elapsed = time.time() - start
            rate = processed / elapsed if elapsed > 0 else 0
            print(
                f"  {processed:,}/{total:,} ({processed / total * 100:.1f}%) "
                f"- {rate:.0f} docs/sec"
            )
            bulk_ops = []

    if bulk_ops:
        col.bulk_write(bulk_ops)
        processed += len(bulk_ops)

    elapsed = time.time() - start
    print(
        f"\nDone in {elapsed:.1f}s. "
        f"Processed: {processed:,}, Enriched: {enriched:,}, "
        f"No IPA: {no_ipa:,}, Errors: {errors:,}"
    )


if __name__ == "__main__":
    reprocess = "--reprocess" in sys.argv
    precompute(reprocess=reprocess)
