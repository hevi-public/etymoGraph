# Integration test suite (SPC-00013)

The integration suite verifies the etymoGraph backend through its HTTP API surface — black-box, against a live `make run` stack. It's organised as four complementary files that catch different classes of regression. Together they form the safety net that lets us refactor the parser, tree builder, and ETL with confidence.

## Files at a glance

| File | What it asserts | Catches |
|---|---|---|
| `test_api_characterization.py` | Live API response equals captured snapshot, byte-for-byte | ANY change, intended or not — every refactor that touches the response surface trips at least one test |
| `test_api_invariants.py` | Structural properties: referential integrity, uniqueness, acyclicity, required fields, label vocabularies | Logic bugs that corrupt response *shape* without breaking byte equality on stale fixtures |
| `test_api_negative.py` | 404 / 422 / empty-result behavior on edges the snapshot suite doesn't reach | Boundary regressions: missing words, malformed params, parameter-validator drift |
| `test_wiktionary_consistency.py` | Live `system_output` covers the hand-encoded `wiktionary_reference` per fixture | Drift from Wiktionary ground truth; serves as the forcing-function for Phase-4 quirk-closure work |

The four together cover every endpoint defined in `backend/app/routers/`: `/api/words`, `/api/etymology/{w}/chain`, `/api/etymology/{w}/tree`, `/api/search`, `/api/concept-map`, `/api/concepts/suggest`, and `/health`.

## Running

```bash
make run                                    # Mongo + backend must be up
make test-integration                       # all four files
make test-integration FLAGS='-k chemistry'  # one fixture across all files
make test-integration FLAGS='-x'            # stop on first failure
ETYMOGRAPH_API=http://other:8000 make test-integration   # different host
```

The session-scope `api_base` fixture in `conftest.py` pings `/health` once at startup; if it's unreachable the entire suite is skipped cleanly with a clear message — useful when you only want unit tests (`make test`) and don't have services up.

## The four-phase TDD loop

The suite is the substrate for an explicit Red-Green-Refactor cycle that spans the codebase, fixture data, and Wiktionary research:

```
   ┌────────────────────┐
   │  Phase 1: Capture  │  Snapshot the live API per fixture word.
   │                    │  system_output is "what we do today."
   └─────────┬──────────┘
             │
   ┌─────────▼──────────┐
   │  Phase 2: Encode   │  Read each fixture's Wiktionary page; fill
   │                    │  wiktionary_reference + alternative_theories.
   └─────────┬──────────┘
             │
   ┌─────────▼──────────┐
   │  Phase 3: Diff     │  Assert system_output covers reference; xfail
   │                    │  where known_gaps documents a divergence.
   └─────────┬──────────┘
             │
   ┌─────────▼──────────┐
   │  Phase 4: Close    │  Refactor service code. Each fix flips an
   │                    │  xfail → pass and a stale-flag test from pass
   │                    │  → fail; the fix-up commit closes the loop.
   └────────────────────┘
```

This is enforced by the test design:

- `test_documented_gap_is_present` watches each `known_gaps.<flag> == true` and fails with "stale flag" the moment the gap symptom disappears. You can't close a gap in code without also flipping its flag — the suite refuses to be green otherwise.
- `test_chain_covers_wiktionary_ancestors` is `xfail` while the gap is open; closing the gap converts it to `XPASS`, which (with `strict=True` or manual review) prompts you to also remove the xfail mark.
- `test_api_characterization` snapshots act as a byte-level tripwire — if you change an endpoint's response shape, the snapshot diffs ARE the API change-log for the PR.

## How to extend

### Add a new fixture (canonical word)

1. Append an entry to `WORDS` in `scripts/collect_wiktionary_examples.py` with `word`, `lang`, observed `quirks_covered`, and a one-line `notes`.
2. `make collect-fixtures FLAGS='--word <newword>'` — generates `tests/fixtures/wiktionary/<newword>.json`.
3. Eyeball the resulting JSON: does the chain look like what Wiktionary shows? If not, that's either a new quirk class or a data gap worth recording.
4. Add corresponding entry to `PHASE2` in `scripts/apply_phase2_reference.py` with the hand-encoded `wiktionary_reference` + `gaps` overrides. Re-run the apply script.
5. `make test-integration` — all four files will now parametrize over the new fixture.

### Add a new test class

Pick the right file:

- **Snapshot-style** (compare live API to a captured value): extend `test_api_characterization.py`. Use `@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)` and `_require_snapshot()` for graceful degradation when older fixtures lack the new key.
- **Structural** (property that should hold regardless of data): extend `test_api_invariants.py`. Pure functions over fixture content; no live API call.
- **Negative path** (404, 422, empty response): extend `test_api_negative.py`. Use `_request()` to get `(status, body)` rather than the snapshot-style `_get()`.
- **Wiktionary-consistency** (a quirk to forgive or assert): extend `test_wiktionary_consistency.py`. Mirror the pattern of `_is_forgiven_absence()` for predicate-based xfails.

### Add a new endpoint

1. Add the route to `backend/app/routers/`.
2. Extend `collect_system_output` in `scripts/collect_wiktionary_examples.py` to capture it per fixture.
3. Add a `test_<endpoint>_matches_snapshot` to `test_api_characterization.py`.
4. Add invariants to `test_api_invariants.py` (response-shape contract).
5. Add 404 / 422 / boundary tests to `test_api_negative.py`.
6. `make collect-fixtures FLAGS=--force` to populate snapshots for existing fixtures.

## Debugging a failure

| Symptom | Most likely cause |
|---|---|
| `test_api_characterization.*_matches_snapshot` fails with a JSON diff | An endpoint's response changed. If intentional, regenerate fixtures and commit the diff. If not, find what code change altered the shape. |
| `test_wiktionary_consistency.test_chain_covers_*` fails (was xfail) | A documented gap was closed — flip the matching `known_gaps` flag in `apply_phase2_reference.py`, re-apply, commit. |
| `test_wiktionary_consistency.test_documented_gap_is_present` fails "stale flag" | A `known_gaps.<flag>` is `true` but the symptom is gone — flip the flag to `false`. |
| `test_api_invariants.test_edge_labels_are_known` fails | A new edge label is being emitted (great if intentional). Add it to `KNOWN_EDGE_LABELS`. |
| `test_api_invariants.test_graph_is_acyclic` fails (was xfail) | The 2-cycle bug is fixed — remove the `@pytest.mark.xfail` decorator. |
| `test_api_negative.*_rejected` fails with status=200 | Parameter validator on the router was loosened. If intentional, update the test. |

## Conventions

- All test functions are sync; the HTTP layer uses stdlib `urllib.request`. No `httpx` / `requests` dependency.
- Fixture loading is shared across files: each declares its own `_fixture_params()` rather than importing — keeps the files independently runnable and makes the fixture path explicit at the top of each.
- `pytest.skip()` is preferred over an empty parametrize set when a fixture predates a test (clear message rather than "0 tests collected"). The `_require_snapshot()` helper in `test_api_characterization.py` is the canonical pattern.
- `xfail(strict=False)` for documented system gaps that *will* close in a future Phase 4 PR. `xfail(strict=True)` for permanent expectations that should never pass.
