# SPC-00013: Wiktionary Example Fixtures

| Field | Value |
|---|---|
| **Status** | draft (Phase 1 in progress) |
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
| `tests/integration/test_api_characterization.py` | NEW — parametrized snapshot tests |
| `tests/integration/conftest.py` | NEW — `api_base` fixture with health-check skip |
| `tests/integration/__init__.py` | NEW — package marker |
| `specs/00013-wiktionary-example-fixtures/spec.md` | NEW — this file |
| `specs/00013-wiktionary-example-fixtures/decision-log.md` | NEW — alternatives considered |
| `Makefile` | Add `collect-fixtures` and `test-integration` targets |

No `backend/app/` changes.

## Verification

1. `make run` → Mongo + backend healthy.
2. `pip install pymongo` (or `pip install -r backend/requirements-dev.txt`) on host.
3. `make collect-fixtures` → 11 JSONs appear in `tests/fixtures/wiktionary/`; one-line summary per word.
4. `python -m json.tool tests/fixtures/wiktionary/*.json > /dev/null` → all parse.
5. **Run the characterization suite**: `make test-integration` → all tests pass (expected by construction; each test asserts the API still returns what was just captured).
6. **Manual mutation drill** (the user, after fixtures and tests exist):
   - Edit `tests/fixtures/wiktionary/wine.json`. In `system_output.chain.edges[0].label`, change `"inh"` to `"bor"`. Re-run `make test-integration`. `test_chain_matches_snapshot[wine]` must FAIL with a clear diff. Revert.
   - Flip `system_output.word_detail.etymology_uncertainty.is_uncertain` for one fixture. Re-run; the matching `test_word_detail_matches_snapshot[<word>]` must fail. Revert.
   - Mutate one nested list field inside `system_output.tree_inh.nodes`. Re-run; the matching tree test must fail. Revert.
   - These three drills together confirm assertions bite at value granularity, not just response shape.
7. `make test-integration ETYMOGRAPH_API=http://elsewhere:8000` → suite skips cleanly with a "not reachable" message.
8. `make test` (existing unit suite) unchanged and still passes.
9. **Human cross-check on data (Phase 2 precondition, not blocking this PR)** — for each fixture, open `meta.wiktionary_url` via WebSearch (sandbox blocks direct fetch), confirm `wiktionary_reference.expected_chain_per_wiktionary` matches the live page. Specifically:
   - `wine.json` → reaches Latin `vinum`.
   - `alchemy.json` → reaches Arabic `اَلْكِيمِيَاء` via Greek; Arabic script renders in node IDs.
   - `dog.json` → `etymology_uncertainty.is_uncertain == true`; `known_gaps.missing_alternative_origins == true`; `wiktionary_reference.alternative_theories` lists the three parallel theories.
   - `cupboard.json` → `known_gaps.missing_compound_components == true`; `system_output.chain.edges == []`; `raw_kaikki.etymology_templates` contains a `compound` template.
   - `orange.json` → record in `meta.notes` which Etymology section (fruit vs. color) was returned.
   - `hound.json` → chain includes a node with `lang == "Proto-Germanic"`; record whether descendant query returned results.
6. `make collect-fixtures FLAGS=--diff` → zero drift on the dump we just collected from.
7. `git diff --stat` → only fixtures + script + spec + Makefile + requirements-dev.txt touched.

## Characterization test suite (Phase 1 of the TDD cycle)

Black-box pytest suite that hits the live API and asserts each response equals the corresponding `system_output` snapshot in the fixture file. The suite runs against `make run` services — no mocking — and is intended to pass by construction (the expected values were captured from this same API). Sensitivity is validated by the user via a manual mutation drill (see the verification section).

**Files:**
- `tests/integration/test_api_characterization.py` — 4 parametrized tests × 1 per fixture = 4 N total cases:
  - `test_word_detail_matches_snapshot[<word>]`
  - `test_chain_matches_snapshot[<word>]`
  - `test_tree_inh_matches_snapshot[<word>]`
  - `test_tree_inh_bor_der_cog_matches_snapshot[<word>]`
- `tests/integration/conftest.py` — `api_base` session fixture; pings `/health` and `pytest.skip()`s the suite if the API is unreachable.
- `tests/integration/__init__.py` — package marker.

**Dependencies:** none new. Uses stdlib `urllib.request` for HTTP and `pytest` (already in `requirements-dev.txt`).

**Runner:** `make test-integration` (also picked up by `make test-all`). Override the API base with `ETYMOGRAPH_API=...` env.

## Tooling for the TDD cycle

The phases below describe how this spec evolves; only Phase 1 is implemented in this PR.

| Phase | Goal | What changes |
|---|---|---|
| 1 (this PR) | Characterize current behavior | Tests added; `system_output` snapshots are the source of truth |
| 2 (later) | Fetch real Wiktionary data, hand-encode `wiktionary_reference` per fixture, identify gaps | Fixture JSONs updated; no test changes |
| 3 (later) | Flip tests from "assert snapshot" to "assert Wiktionary consistency for non-gapped items" | Tests modified — go red where the system diverges from Wiktionary |
| 4 (later) | Refactor services to close each gap (Q1, Q2, Q6, Q7…) | Service code changes — tests go green |

## Out of scope (future phases)

- Phase 2 / 3 / 4 above — each phase gets its own PR, possibly its own follow-up spec.
- Mock-DB strategy (mongomock-motor or testcontainers): defer until isolation is a problem.
- Service-layer unit tests (filling `backend/tests/test_tree_builder.py` TODO stubs): tackle when those services are refactored in Phase 4.
