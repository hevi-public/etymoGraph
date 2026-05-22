# SPC-00011: Wiktionary Example Fixtures

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-05-22 |
| **Modifies** | — |
| **Modified-by** | — |

## Summary

Collect a curated set of word-level fixtures that snapshot our current API output alongside hand-encoded ground truth from Wiktionary. These fixtures are the substrate for a follow-up integration-test PR. This spec covers **collection only** — the test runner itself is out of scope.

The fixtures are designed to expose specific Wiktionary quirks our Kaikki-derived pipeline either flattens, omits, or surfaces in templates we do not currently follow.

## Quirks under test

Each fixture word is selected to exercise at least one quirk class. Codes referenced from `tests/fixtures/wiktionary/README.md`.

| Code | Quirk | Example word | What our pipeline does today |
|---|---|---|---|
| Q1 | Disjunctive / "either X or Y" origins | `dog` | Classifier flags `is_uncertain`; only the first template surfaces in `/chain` |
| Q2 | Compounds / affixed forms back to base words | `cupboard`, `blackbird` | `compound`/`af`/`+` not in `ANCESTRY_TYPES`; appear only in `related_mentions` |
| Q3 | Dead / missing links (reconstructed proto-forms) | `hound` chain → `*hundaz`, `*ḱwṓ` | Coverage depends on whether Kaikki has the reconstruction doc |
| Q4 | Multiple Etymology sections per page | `orange` (fruit vs. color) | `find_one((word, lang))` picks whichever doc Mongo returns first |
| Q5 | Foreign-script ancestors | `alchemy` → `اَلْكِيمِيَاء`; `orange` → `नारङ्ग` | `node_id` round-trip through URL/Mongo/vis.js untested |
| Q6 | Calques and "influenced by" | `orange` | No edge label for `cal`; "influenced by" dropped entirely |
| Q7 | Doublets | `alchemy` / `chemistry` | No graph representation for sister-via-shared-root |
| Q8 | Prose-only intermediate forms | `hound`'s "Pre-Germanic *kun-tós" | Skipped — no structured template |
| Q9 | Cognates listed inline with ancestors | `hound`, `fire` | `extract_cognates` separates them; assertable |
| Q10 | POS-specific etymologies | `orange` adjective vs. noun | One doc per `(word, lang, pos)`; chain endpoint ignores POS |
| Q11 | "Of unknown origin" terminals | `dog`, `chuckle` | Chain ends silently; verify no 404/error |
| Q12 | Kaikki snapshot lag vs. live Wiktionary | all | Document with `meta.kaikki_dump_date` |

## Word set

| Word | Quirks covered |
|---|---|
| `wine` | clean baseline (`inh` chain) |
| `hound` | Q3, Q8, Q9 |
| `cheese` | clean borrowing baseline |
| `fire` | Q9, deep PIE |
| `alchemy` | Q5, Q7 |
| `chemistry` | Q7 |
| `dog` | Q1, Q11 |
| `cupboard` | Q2 |
| `blackbird` | Q2 |
| `orange` | Q4, Q5, Q6, Q10 |
| `chuckle` | Q11, coined |

## Fixture schema

One file per word at `tests/fixtures/wiktionary/{word}.json`. Three layers:

- **`wiktionary_reference`** — hand-encoded ground truth from the live Wiktionary page. Filled by the human reviewer during the cross-check pass.
- **`system_output`** — exact responses from `/api/words/{w}`, `/api/etymology/{w}/chain`, `/api/etymology/{w}/tree?types=inh`, `/api/etymology/{w}/tree?types=inh,bor,der,cog`. Populated automatically by the collector.
- **`known_gaps`** — boolean flags marking documented discrepancies between reference and output that are expected today. Each flag flips to `false` as the underlying gap is closed by a future feature.
- **`raw_kaikki`** — projection of the Mongo doc (etymology_templates, etymology_text, senses[].glosses, sounds, phonetic) so the input to the system is snapshotted alongside its output.
- **`meta`** — provenance: spec id, Kaikki dump date, Wiktionary URL, ISO timestamp, etymograph HEAD sha.

Full schema in `tests/fixtures/wiktionary/README.md`.

## Collection script

`scripts/collect_wiktionary_examples.py` — sync Python, runs from host against `make run` services:

- Mongo: `mongodb://localhost:27017/etymology` (override via `MONGO_URI` env).
- API: `http://localhost:8000` (override via `ETYMOGRAPH_API` env).
- Dependencies: `pymongo` (host install) + stdlib (`urllib.request`, `json`, `argparse`).
- CLI: `--word <w>`, `--all`, `--force` (overwrite), `--diff` (no-write drift detector for future CI).
- Heuristically pre-fills `known_gaps.missing_compound_components` when `raw_kaikki.etymology_templates` contains a `compound`/`af`/`+` template but `system_output.chain.edges` is empty.
- Prints a one-line summary per word (chain node count, edge count, uncertainty flag, detected gaps) for the human eyeball pass.

## Files Changed

| File | Changes |
|---|---|
| `scripts/collect_wiktionary_examples.py` | NEW — collector script |
| `backend/requirements-dev.txt` | Add `pymongo` (script dep) |
| `tests/fixtures/wiktionary/README.md` | NEW — schema, quirk codes Q1–Q12, regeneration command |
| `tests/fixtures/wiktionary/{word}.json` | NEW — 11 fixtures (generated locally, committed after human cross-check) |
| `specs/00011-wiktionary-example-fixtures/spec.md` | NEW — this file |
| `specs/00011-wiktionary-example-fixtures/decision-log.md` | NEW — alternatives considered |
| `Makefile` | Add `collect-fixtures` target |

No `backend/app/` changes. No test runner code in this PR.

## Verification

1. `make run` → Mongo + backend healthy.
2. `pip install pymongo` (or `pip install -r backend/requirements-dev.txt`) on host.
3. `make collect-fixtures` → 11 JSONs appear in `tests/fixtures/wiktionary/`; one-line summary per word.
4. `python -m json.tool tests/fixtures/wiktionary/*.json > /dev/null` → all parse.
5. **Human cross-check (required before commit)** — for each fixture, open the corresponding `meta.wiktionary_url` via WebSearch (sandbox blocks direct fetch), confirm `wiktionary_reference.expected_chain_per_wiktionary` matches the live page. Specifically:
   - `wine.json` → reaches Latin `vinum`.
   - `alchemy.json` → reaches Arabic `اَلْكِيمِيَاء` via Greek; Arabic script renders in node IDs.
   - `dog.json` → `etymology_uncertainty.is_uncertain == true`; `known_gaps.missing_alternative_origins == true`; `wiktionary_reference.alternative_theories` lists the three parallel theories.
   - `cupboard.json` → `known_gaps.missing_compound_components == true`; `system_output.chain.edges == []`; `raw_kaikki.etymology_templates` contains a `compound` template.
   - `orange.json` → record in `meta.notes` which Etymology section (fruit vs. color) was returned.
   - `hound.json` → chain includes a node with `lang == "Proto-Germanic"`; record whether descendant query returned results.
6. `make collect-fixtures FLAGS=--diff` → zero drift on the dump we just collected from.
7. `git diff --stat` → only fixtures + script + spec + Makefile + requirements-dev.txt touched.

## Out of scope (follow-up PRs)

- `backend/tests/test_integration_api.py` and the conftest fixture loader.
- Real test-DB strategy (mongomock vs. testcontainers vs. seeded dev Mongo).
- `make test-integration` target.
- Pipeline improvements to close Q1, Q2, Q6, Q7 — each likely deserves its own spec.
