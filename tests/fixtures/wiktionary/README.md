# Wiktionary Example Fixtures (SPC-00013)

Snapshots of API output for a curated word set, alongside hand-encoded ground truth from Wiktionary. Substrate for the integration tests planned in the follow-up PR.

## Quirk codes

Each fixture's `quirks_covered` field references one or more of these. See `specs/00013-wiktionary-example-fixtures/spec.md` for full discussion.

| Code | Quirk |
|---|---|
| Q1  | Disjunctive / "either X or Y" origins |
| Q2  | Compounds / affixed forms back to base words |
| Q3  | Dead / missing links (reconstructed proto-forms) |
| Q4  | Multiple Etymology sections per page |
| Q5  | Foreign-script ancestors |
| Q6  | Calques and "influenced by" |
| Q7  | Doublets |
| Q8  | Prose-only intermediate forms |
| Q9  | Cognates listed inline with ancestors |
| Q10 | POS-specific etymologies |
| Q11 | "Of unknown origin" terminals |
| Q12 | Kaikki snapshot lag vs. live Wiktionary |

## Schema

```jsonc
{
  "meta": {
    "spec": "SPC-00013",
    "kaikki_source_url": "https://kaikki.org/...",
    "kaikki_dump_date": null,                  // set via KAIKKI_DUMP_DATE env at collection time
    "wiktionary_url": "https://en.wiktionary.org/wiki/dog",
    "wiktionary_revision_seen": null,          // oldid if known, else null
    "collected_at": "2026-05-22T14:32:00+00:00",
    "etymograph_git_sha": "...",
    "notes": "..."
  },
  "query": { "word": "dog", "lang": "English" },
  "quirks_covered": ["Q1", "Q11"],

  // Hand-encoded by the human reviewer during the cross-check pass.
  // Empty after fresh collection; populated before commit.
  "wiktionary_reference": {
    "etymology_section_text_excerpt": "From Middle English dogge ... of uncertain origin. Possibly from ...",
    "expected_chain_per_wiktionary": [
      {"lang": "Middle English", "word": "dogge"},
      {"lang": "Old English",    "word": "docga", "note": "uncertain"}
    ],
    "alternative_theories": [
      {"summary": "from Old English dox", "kaikki_template_present": false}
    ]
  },

  // Projection of the Mongo doc — input to the system, snapshotted so we can
  // tell whether a future drift is input-side (Kaikki updated) or output-side
  // (our pipeline changed).
  "raw_kaikki": {
    "word": "...", "lang": "...", "lang_code": "...", "pos": "...",
    "etymology_text": "...",
    "etymology_templates": [ ... ],
    "senses": [ ... ],
    "sounds": [ ... ],
    "phonetic": { ... }
  },

  // Exact responses from the live API at collection time.
  "system_output": {
    "word_detail":            { /* /api/words/{word}?lang=... */ },
    "chain":                  { "nodes": [...], "edges": [...] },
    "tree_inh":               { "nodes": [...], "edges": [...] },
    "tree_inh_bor_der_cog":   { "nodes": [...], "edges": [...] }
  },

  // Documented deltas between wiktionary_reference and system_output that
  // are expected today. Each flag flips to false as the underlying gap is
  // closed by a future spec.
  "known_gaps": {
    "missing_alternative_origins":         true,   // Q1
    "missing_compound_components":         false,  // Q2
    "missing_calques":                     false,  // Q6
    "missing_doublet_link":                false,  // Q7
    "foreign_script_roundtrip_unverified": false,  // Q5
    "notes": "Heuristic pre-fill — human reviewer should adjust during cross-check."
  }
}
```

## Regenerating fixtures

```bash
# Preconditions: make run, and Mongo populated (make load).
pip install pymongo

# Collect all configured words (writes only missing files):
make collect-fixtures

# Overwrite existing fixtures:
python scripts/collect_wiktionary_examples.py --all --force

# Re-collect one word:
python scripts/collect_wiktionary_examples.py --word dog --force

# Drift check (no writes; exit 1 if any fixture differs ignoring timestamp):
python scripts/collect_wiktionary_examples.py --all --diff

# Override defaults (e.g., when Mongo or backend is on a non-default port):
MONGO_URI=mongodb://localhost:27017/etymology \
ETYMOGRAPH_API=http://localhost:8000 \
KAIKKI_DUMP_DATE=2026-04-01 \
python scripts/collect_wiktionary_examples.py --all
```

## Human cross-check workflow

After regeneration, **before committing**:

1. Open each fixture's `meta.wiktionary_url` (use WebSearch — sandbox blocks direct WebFetch).
2. Read the Etymology section. Fill `wiktionary_reference.etymology_section_text_excerpt` with the first 1–3 sentences.
3. Fill `wiktionary_reference.expected_chain_per_wiktionary` with the primary ancestry chain as Wiktionary presents it.
4. For words with `Q1` (disjunctive origins), fill `wiktionary_reference.alternative_theories` with each "perhaps from..." / "possibly..." branch.
5. Review the heuristic flags in `known_gaps`. Adjust where the heuristic guessed wrong. Add free-form `notes`.
6. Commit.

The follow-up integration-test PR will then assert:
- `system_output` matches the committed snapshot byte-for-byte (regression guard).
- For each `known_gaps.* == false`, `system_output` covers the corresponding `wiktionary_reference` items (correctness guard for handled quirks).
