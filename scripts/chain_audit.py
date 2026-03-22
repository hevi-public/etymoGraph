#!/usr/bin/env python3
"""Sprint 1: Trace etymology chains for sample words and measure breakage.

Connects directly to MongoDB, extracts ancestry templates for each word,
and checks whether each ancestor exists as a document in the DB.
Categorizes mismatches and outputs statistics.
"""

import unicodedata
from pymongo import MongoClient

SAMPLE_WORDS = [
    "wine", "cheese", "water", "mother", "fire", "father", "brother", "sister",
    "house", "bread", "milk", "fish", "stone", "tree", "sun", "moon", "star",
    "earth", "night", "day", "hand", "eye", "heart", "blood", "bone",
    "name", "king", "sword", "horse", "wolf", "bear", "door", "ship",
    "gold", "silver", "iron", "salt", "wheel", "bridge", "church", "book",
    "love", "death", "god", "man", "woman", "child", "dog", "cat", "bird",
]

ANCESTRY_TYPES = {"inh", "bor", "der"}


def strip_macrons(word: str) -> str:
    """Remove macrons (and other combining marks) from a word."""
    nfkd = unicodedata.normalize("NFKD", word)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def strip_asterisk(word: str) -> str:
    """Remove leading asterisk from reconstructed forms."""
    return word.lstrip("*")


def classify_mismatch(template_word: str, db_word: str | None, lang_code: str) -> str:
    """Classify why a template word doesn't match a DB document."""
    if db_word is not None:
        return "exact_match"

    # Would stripping asterisk fix it?
    no_asterisk = strip_asterisk(template_word)
    if no_asterisk != template_word:
        return "asterisk_prefix"

    # Would stripping macrons fix it?
    no_macrons = strip_macrons(template_word)
    if no_macrons != template_word:
        return "macron_diacritics"

    return "missing_entirely"


def extract_ancestry(doc: dict) -> list[dict]:
    """Extract ordered ancestry templates from a document."""
    ancestry = []
    for tmpl in doc.get("etymology_templates") or []:
        if tmpl.get("name") not in ANCESTRY_TYPES:
            continue
        args = tmpl.get("args", {})
        lang_code = args.get("2", "")
        word = args.get("3", "")
        if not word or not lang_code:
            continue
        ancestry.append({
            "word": word,
            "lang_code": lang_code,
            "type": tmpl["name"],
        })
    return ancestry


def main():
    import os
    mongo_host = os.environ.get("MONGO_HOST", "localhost")
    client = MongoClient(f"mongodb://{mongo_host}:27017")
    db = client["etymology"]
    col = db["words"]

    # Build language code -> name map
    lang_map = {}
    for doc in db["languages"].find({}, {"_id": 0, "lang_code": 1, "lang": 1}):
        if "lang_code" in doc and "lang" in doc:
            lang_map[doc["lang_code"]] = doc["lang"]

    total_ancestors = 0
    exact_matches = 0
    mismatches = {"asterisk_prefix": 0, "macron_diacritics": 0,
                  "different_form": 0, "missing_entirely": 0}
    # Track which normalization would have helped
    asterisk_resolved = 0
    macron_resolved = 0
    both_resolved = 0

    word_results = []

    for word in SAMPLE_WORDS:
        doc = col.find_one(
            {"word": word, "lang": "English"},
            {"_id": 0, "etymology_templates": 1, "etymology_text": 1},
        )
        if not doc:
            word_results.append({"word": word, "status": "NOT_IN_DB", "chain": []})
            continue

        ancestry = extract_ancestry(doc)
        if not ancestry:
            word_results.append({"word": word, "status": "NO_ANCESTRY", "chain": []})
            continue

        chain_info = []
        for anc in ancestry:
            total_ancestors += 1
            tw = anc["word"]
            lc = anc["lang_code"]
            lang_name = lang_map.get(lc, lc)

            # Check exact match
            found = col.find_one({"word": tw, "lang_code": lc}, {"_id": 0, "word": 1})

            if found:
                exact_matches += 1
                chain_info.append(f"  OK  {anc['type']} {lc}:{tw}")
                continue

            # Try normalizations
            no_ast = strip_asterisk(tw)
            no_mac = strip_macrons(tw)
            no_both = strip_macrons(strip_asterisk(tw))

            found_ast = col.find_one({"word": no_ast, "lang_code": lc}, {"_id": 0, "word": 1}) if no_ast != tw else None
            found_mac = col.find_one({"word": no_mac, "lang_code": lc}, {"_id": 0, "word": 1}) if no_mac != tw else None
            found_both = col.find_one({"word": no_both, "lang_code": lc}, {"_id": 0, "word": 1}) if no_both != tw else None

            if found_ast:
                mismatches["asterisk_prefix"] += 1
                asterisk_resolved += 1
                chain_info.append(f"  AST {anc['type']} {lc}:{tw} -> DB has '{no_ast}'")
            elif found_mac:
                mismatches["macron_diacritics"] += 1
                macron_resolved += 1
                chain_info.append(f"  MAC {anc['type']} {lc}:{tw} -> DB has '{no_mac}'")
            elif found_both:
                mismatches["macron_diacritics"] += 1
                both_resolved += 1
                chain_info.append(f"  A+M {anc['type']} {lc}:{tw} -> DB has '{no_both}'")
            else:
                mismatches["missing_entirely"] += 1
                chain_info.append(f"  MIS {anc['type']} {lc}:{tw} (not found under any normalization)")

        word_results.append({"word": word, "status": "OK", "chain": chain_info})

    # Print results
    print("=" * 70)
    print("SPRINT 1: ETYMOLOGY CHAIN BREAKAGE AUDIT")
    print("=" * 70)
    print()

    for wr in word_results:
        if wr["status"] != "OK":
            print(f"[{wr['word']}] — {wr['status']}")
        else:
            print(f"[{wr['word']}]")
            for line in wr["chain"]:
                print(line)
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Words sampled:        {len(SAMPLE_WORDS)}")
    print(f"Words found in DB:    {sum(1 for w in word_results if w['status'] != 'NOT_IN_DB')}")
    print(f"Words with ancestry:  {sum(1 for w in word_results if w['status'] == 'OK')}")
    print()
    print(f"Total ancestor refs:  {total_ancestors}")
    print(f"Exact matches:        {exact_matches} ({100*exact_matches/max(total_ancestors,1):.1f}%)")
    print(f"Asterisk mismatch:    {mismatches['asterisk_prefix']} (resolved by stripping *)")
    print(f"Macron mismatch:      {mismatches['macron_diacritics']} (resolved by stripping diacritics)")
    print(f"  - asterisk+macron:  {both_resolved} (needed both)")
    print(f"Missing entirely:     {mismatches['missing_entirely']} (no match under any normalization)")
    print()
    resolvable = asterisk_resolved + macron_resolved + both_resolved
    print(f"Resolvable by normalization: {resolvable}/{total_ancestors - exact_matches} broken links")
    print(f"Potential match rate:  {100*(exact_matches + resolvable)/max(total_ancestors,1):.1f}%")

    client.close()


if __name__ == "__main__":
    main()
