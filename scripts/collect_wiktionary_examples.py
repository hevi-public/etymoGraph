#!/usr/bin/env python3
"""Collect Wiktionary-example fixtures for SPC-00013.

Snapshots the current API output (`/api/words`, `/api/etymology/.../chain`,
`/api/etymology/.../tree`) for a curated word set, alongside the raw Kaikki
document. Each fixture also reserves space for hand-encoded Wiktionary ground
truth and an explicit gap inventory — see specs/00013-wiktionary-example-fixtures/
for the rationale.

Run against a live `make run` stack (Mongo on :27017, backend on :8000).

Usage:
    pip install pymongo
    python scripts/collect_wiktionary_examples.py --all
    python scripts/collect_wiktionary_examples.py --word dog --force
    python scripts/collect_wiktionary_examples.py --all --diff
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pymongo import MongoClient


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "wiktionary"
SPEC_ID = "SPC-00013"

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/etymology")
API_BASE = os.environ.get("ETYMOGRAPH_API", "http://localhost:8000").rstrip("/")
KAIKKI_URL = "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"

# Each entry: (word, lang, quirks_covered, notes). See spec.md for quirk codes.
WORDS: list[dict[str, Any]] = [
    {
        "word": "wine",
        "lang": "English",
        "quirks": ["Q13"],
        "notes": "inh chain → OE wīn → Latin vīnum; ancestors carry macrons.",
    },
    {
        "word": "hound",
        "lang": "English",
        "quirks": ["Q3", "Q8", "Q9", "Q13"],
        "notes": "Proto-Germanic *hundaz; pre-Germanic prose; asterisk + macron in templates.",
    },
    {
        "word": "cheese",
        "lang": "English",
        "quirks": ["Q13"],
        "notes": "Borrowing ← Latin cāseus; OE ċīese has macron + diacritic.",
    },
    {
        "word": "fire",
        "lang": "English",
        "quirks": ["Q9"],
        "notes": "Deep PIE; cognates in Sanskrit/Greek/Hittite.",
    },
    {
        "word": "alchemy",
        "lang": "English",
        "quirks": ["Q5", "Q7"],
        "notes": "Foreign-script terminal (Arabic); doublet of chemistry.",
    },
    {
        "word": "chemistry",
        "lang": "English",
        "quirks": ["Q7"],
        "notes": "Doublet of alchemy via different Greek path.",
    },
    {
        "word": "dog",
        "lang": "English",
        "quirks": ["Q1", "Q11"],
        "notes": "Disjunctive origins; uncertain etymology.",
    },
    {
        "word": "cupboard",
        "lang": "English",
        "quirks": ["Q2"],
        "notes": "Compound (cup + board) — should expose Q2 gap.",
    },
    {
        "word": "blackbird",
        "lang": "English",
        "quirks": ["Q2"],
        "notes": "Second compound — confirms Q2 is systematic.",
    },
    {
        "word": "orange",
        "lang": "English",
        "quirks": ["Q4", "Q5", "Q6", "Q10"],
        "notes": "Multi-etymology; Sanskrit terminal; calque; POS split.",
    },
    {
        "word": "chuckle",
        "lang": "English",
        "quirks": ["Q11"],
        "notes": "Coined word ('Lewis Carroll'); no traditional ancestor.",
    },
    # --- Phase 4 fixture expansion: quirk-class breadth ---------------
    {
        "word": "smog",
        "lang": "English",
        "quirks": ["Q2"],
        "notes": "Blend of smoke + fog (coined ~1905). Exercises `blend` template.",
    },
    {
        "word": "brunch",
        "lang": "English",
        "quirks": ["Q2"],
        "notes": "Blend of breakfast + lunch (attested 1895 UK / 1930 US). Second blend datapoint.",
    },
    {
        "word": "sandwich",
        "lang": "English",
        "quirks": ["Q11"],
        "notes": "Eponym — named after John Montagu, 4th Earl of Sandwich. "
                 "No traditional linguistic-ancestor chain; etymology is biographical.",
    },
    {
        "word": "karaoke",
        "lang": "English",
        "quirks": ["Q5"],
        "notes": "Modern borrowing from Japanese カラオケ (= 空 'empty' + オケ, "
                 "clipping of オーケストラ 'orchestra' ← English orchestra). "
                 "Recursive borrowing (orchestra → JP → EN); Japanese script.",
    },
    {
        "word": "laser",
        "lang": "English",
        "quirks": ["Q11"],
        "notes": "Acronym: Light Amplification by Stimulated Emission of Radiation "
                 "(1960). Components are common English words, not ancestors.",
    },
    {
        "word": "cockroach",
        "lang": "English",
        "quirks": ["Q5"],
        "notes": "Borrowed from Spanish cucaracha; reanalysed by folk etymology as "
                 "cock + roach. Folk-etymology relationship not captured as a template.",
    },
    {
        "word": "Hund",
        "lang": "German",
        "quirks": ["Q13"],
        "notes": "Non-English query word — stresses lang handling beyond English. "
                 "Same PIE root as 'hound' (Proto-Germanic *hundaz ← PIE *ḱwṓ); "
                 "ancestors carry asterisks + macrons.",
    },
]

# Tree configurations captured for each word.
TREE_CONFIGS = [
    ("tree_inh", "inh"),
    ("tree_inh_bor_der_cog", "inh,bor,der,cog"),
]

RAW_KAIKKI_FIELDS = (
    "word",
    "lang",
    "lang_code",
    "pos",
    "etymology_text",
    "etymology_templates",
    "senses",
    "sounds",
    "phonetic",
)

GAP_TEMPLATE_NAMES = {"compound", "af", "affix", "suffix", "prefix", "blend", "+"}
CALQUE_TEMPLATE_NAMES = {"cal", "calque"}
DOUBLET_TEMPLATE_NAMES = {"doublet"}


def fetch_raw_kaikki(client: MongoClient, word: str, lang: str) -> dict[str, Any] | None:
    """Return the Mongo doc for (word, lang), projected to fixture-relevant fields."""
    projection = dict.fromkeys(RAW_KAIKKI_FIELDS, 1)
    projection["_id"] = 0
    return client.get_database().words.find_one({"word": word, "lang": lang}, projection)


def http_get_json(path: str) -> Any:
    """GET a JSON endpoint on the live API, returning parsed body or {'__error__': ...}."""
    url = f"{API_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {
            "__error__": f"HTTP {e.code}",
            "url": url,
            "body": e.read().decode("utf-8", errors="replace")[:500],
        }
    except Exception as e:
        return {"__error__": str(e), "url": url}


def collect_system_output(word: str, lang: str) -> dict[str, Any]:
    """Hit the four endpoints captured per fixture."""
    qs = urllib.parse.quote(word)
    lang_qs = urllib.parse.quote(lang)
    output: dict[str, Any] = {
        "word_detail": http_get_json(f"/api/words/{qs}?lang={lang_qs}"),
        "chain": http_get_json(f"/api/etymology/{qs}/chain?lang={lang_qs}"),
    }
    for key, types in TREE_CONFIGS:
        output[key] = http_get_json(
            f"/api/etymology/{qs}/tree?lang={lang_qs}&types={urllib.parse.quote(types)}"
        )
    return output


def detect_gaps(raw: dict[str, Any] | None, output: dict[str, Any]) -> dict[str, Any]:
    """Pre-fill known_gaps flags heuristically. Human reviewer adjusts as needed."""
    templates = (raw or {}).get("etymology_templates", []) or []
    template_names = {t.get("name") for t in templates if isinstance(t, dict)}

    chain = output.get("chain") or {}
    chain_edges = chain.get("edges") or []
    word_detail = output.get("word_detail") or {}
    uncertainty = (word_detail.get("etymology_uncertainty") or {}).get("is_uncertain", False)

    has_compound_template = bool(template_names & GAP_TEMPLATE_NAMES)
    has_calque_template = bool(template_names & CALQUE_TEMPLATE_NAMES)
    has_doublet_template = bool(template_names & DOUBLET_TEMPLATE_NAMES)

    return {
        "missing_alternative_origins": uncertainty and len(chain_edges) <= 1,
        "missing_compound_components": has_compound_template and not chain_edges,
        "missing_calques": has_calque_template,
        "missing_doublet_link": has_doublet_template,
        "foreign_script_roundtrip_unverified": False,
        "notes": "Heuristic pre-fill — human reviewer should adjust during cross-check.",
    }


def git_head_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_fixture(entry: dict[str, Any], client: MongoClient) -> dict[str, Any]:
    """Assemble the full fixture dict for one word."""
    word, lang = entry["word"], entry["lang"]
    wiktionary_url = f"https://en.wiktionary.org/wiki/{urllib.parse.quote(word)}"

    raw = fetch_raw_kaikki(client, word, lang)
    system_output = collect_system_output(word, lang)
    gaps = detect_gaps(raw, system_output)

    return {
        "meta": {
            "spec": SPEC_ID,
            "kaikki_source_url": KAIKKI_URL,
            "kaikki_dump_date": os.environ.get("KAIKKI_DUMP_DATE"),
            "wiktionary_url": wiktionary_url,
            "wiktionary_revision_seen": None,
            "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "etymograph_git_sha": git_head_sha(),
            "notes": entry["notes"],
        },
        "query": {"word": word, "lang": lang},
        "quirks_covered": entry["quirks"],
        "wiktionary_reference": {
            "etymology_section_text_excerpt": None,
            "expected_chain_per_wiktionary": [],
            "alternative_theories": [],
        },
        "raw_kaikki": raw,
        "system_output": system_output,
        "known_gaps": gaps,
    }


def serialize(fixture: dict[str, Any]) -> str:
    """Stable JSON formatting for diff-friendly fixtures."""
    return json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_fixture(fixture: dict[str, Any], path: Path, force: bool) -> str:
    if path.exists() and not force:
        return "skip (exists)"
    path.write_text(serialize(fixture), encoding="utf-8")
    return "wrote"


def diff_fixture(fixture: dict[str, Any], path: Path) -> str:
    if not path.exists():
        return "missing (no baseline)"
    current = path.read_text(encoding="utf-8")
    fresh = serialize(fixture)
    if current == fresh:
        return "no drift"
    # Diff omitting meta.collected_at (always different) for a meaningful report.
    fresh_doc = json.loads(fresh)
    fresh_doc["meta"]["collected_at"] = json.loads(current)["meta"]["collected_at"]
    if serialize(fresh_doc) == current:
        return "no drift (only timestamp)"
    return "DRIFT"


def summarize(word: str, fixture: dict[str, Any], action: str) -> str:
    chain = fixture["system_output"].get("chain") or {}
    nodes = len(chain.get("nodes") or [])
    edges = len(chain.get("edges") or [])
    uncertain = (
        (fixture["system_output"].get("word_detail") or {})
        .get("etymology_uncertainty", {})
        .get("is_uncertain")
    )
    flags = [k for k, v in fixture["known_gaps"].items() if v is True]
    return (
        f"  {word:12s} chain={nodes}n/{edges}e "
        f"uncertain={bool(uncertain)} gaps={flags or '-'} [{action}]"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Collect all configured words.")
    group.add_argument("--word", help="Collect a single word from the configured set.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing fixture files.")
    parser.add_argument(
        "--diff", action="store_true", help="Do not write; report drift against existing fixtures."
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = WORDS if args.all else [w for w in WORDS if w["word"] == args.word]
    if not targets:
        sys.exit(f"Unknown word '{args.word}'. Configured: {[w['word'] for w in WORDS]}")

    try:
        from pymongo import MongoClient
    except ImportError:
        sys.exit("pymongo is required: pip install pymongo")

    print(f"Mongo: {MONGO_URI}")
    print(f"API:   {API_BASE}")
    print(f"Out:   {OUT_DIR}")
    print()

    client = MongoClient(MONGO_URI)
    has_drift = False
    for entry in targets:
        word = entry["word"]
        path = OUT_DIR / f"{word}.json"
        fixture = build_fixture(entry, client)
        if args.diff:
            action = diff_fixture(fixture, path)
            if action == "DRIFT":
                has_drift = True
        else:
            action = write_fixture(fixture, path, args.force)
        print(summarize(word, fixture, action))

    if args.diff and has_drift:
        print("\nDrift detected. Re-run without --diff (and with --force) to update fixtures.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
