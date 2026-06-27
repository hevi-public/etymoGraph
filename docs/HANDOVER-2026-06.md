# Handover — Audit Roadmap Implementation

| | |
|---|---|
| **Date** | 2026-06-27 |
| **From** | Audit + spec-drafting pass (see [`docs/AUDIT-2026-06.md`](AUDIT-2026-06.md)) |
| **To** | Implementation workers (parallel) |
| **Branch at handover** | `claude/vigorous-hellman-1d756a` (a worktree) |
| **State** | **Design only — no app behavior changed.** Specs `00014`–`00020` are `draft`; remediation of the dead G6 spec line + doc drift is already applied. |

---

## 1. Read first (orientation, ~10 min)

1. [`docs/AUDIT-2026-06.md`](AUDIT-2026-06.md) — findings (Part A), remediation (Part B), the audience-tagged feature roadmap (Part C). **This is the why.**
2. The spec for your package under `specs/NNNNN-*/spec.md` + its `decision-log.md` — **this is the what.**
3. `CLAUDE.md` → "Specs", "Git Commits", "Code Review Process", "Conventions" — the house rules every package must follow.

**The current working tree is uncommitted** (the audit doc + specs `00005`/`00006` deprecation + `00014`–`00020` + doc-drift edits). Whoever dispatches should **commit this design pass first** so workers branch from a clean base. Suggested: one commit `docs: 2026-06 feature audit + roadmap specs (00014–00020), deprecate G6 line`.

---

## 2. Environment prerequisites (every package)

- `make setup` (one-time) then `make run` — brings up MongoDB + backend + frontend. **MongoDB was NOT running during the audit**, so:
  - Any package touching descendants/coverage **must first verify live data** (see SPC-00014 gotchas).
  - Tier-1 / Acceptance / `live` tests and the data-coverage numbers in the audit need a loaded DB.
- `make setup-dev` — linters + pre-commit hooks (Ruff, ESLint). **All new code must pass `make lint`.**
- `make test` (pytest) · `make test-frontend` (Vitest) · `make test-e2e` (Playwright, needs `make run`).
- **`httpx` is not yet installed** and is required by SPC-00020's acceptance tier — add to `backend/requirements-dev.txt` (see SPC-00020).

---

## 3. Dependency graph & suggested parallelization

```
FOUNDATION (start immediately, unblocks the rest)
  ├─ SPC-00020  Tiered testing — Steps 1-3 + acceptance net   ← do BEFORE/ALONGSIDE 00014 impl
  └─ (G6 remediation: DONE — nothing to implement)

KEYSTONE
  └─ SPC-00014  Native descendants + inflection search        ← needs 00020's seam; unblocks 00015/00016

FLAGSHIP (after 00014)
  ├─ SPC-00015  Doublets            (depends on 00014)
  └─ SPC-00016  Sound-change view   (depends on 00002 + 00014)

INDEPENDENT (start anytime, no blockers)
  ├─ SPC-00017  Export & interop
  └─ SPC-00019  Accessibility & UX baseline

PARTLY-BLOCKED
  └─ SPC-00018  Guided discovery — WOTD/random/tours independent; "did you know" needs 00015
```

**Three packages are startable in parallel right now with zero cross-dependencies: `00020` (Steps 1-3), `00017`, `00019`.** `00014` should begin once `00020`'s injectable seam exists (or the same worker lands both).

> Specs are `draft`. Recommend a quick human **draft → approved** gate per `CLAUDE.md`'s lifecycle before a worker starts coding; flip to `implemented` on merge, and append the spec ID to `docs/FEATURES.md`.

---

## 4. Work packages

Each package = one branch, one PR. Severity from the audit. "Ready" = no unmet dependency.

### SPC-00020 — Tiered Testing Architecture · `[foundation]` · Ready
- **Goal:** one injectable Mongo seam + four runnable tiers (tier0/1/2/acceptance) so the core engine is testable without a live stack. Closes audit **R2**.
- **Do it staged (the spec is explicit):** **Steps 1-3 first** — move the Motor client out of import time into a `lifespan` (`app.state.db`), add `Depends` providers in `database.py`, convert the 6 router call-sites. *Reversible, ~4 files.* Then land the **hermetic acceptance net** reusing the SPC-00013 fixtures. **Then Step 4** (the `WordsRepository` port) — larger, non-reversible; do it behind the acceptance net.
- **Key files:** `backend/app/database.py`, `main.py`, `routers/*`, new `backend/app/repository.py`, `services/tree_builder.py` + `concept_resolver.py` + `lang_cache.py`, `backend/tests/conftest.py`, `pyproject.toml`, `backend/requirements-dev.txt`, `Makefile`.
- **Gotchas (verified by adversarial review — do not relearn the hard way):**
  - Steps 1-3 alone do **not** give no-Mongo Tier-2; that needs the port (Step 4). Don't conflate them.
  - **Collation is the one operator mongomock silently ignores** → `suggest_concepts` is Tier-1/real-Mongo-only with a **hard skip**. mongomock is an optional fast lane, never the authority.
  - Motor binds to the event loop at client construction → **build the client inside `lifespan`/fixtures, never at import**, or pytest-asyncio loops mismatch.
  - The two **module-global caches** (`lang_cache._code_to_name/_name_to_code`, `concept_resolver._concept_cache`) leak across tests → **mandatory autouse reset fixture**. `lang_cache` is read synchronously inside pure functions, so keep it a global + reset (don't try to fold it behind the async repo without a separately-costed `LangResolver`).
  - The seam touches sibling collections via `self.col.database["etymology_edges"]` and `...get_collection("languages")` → the port must expose these as first-class methods.

### SPC-00014 — Native Descendants & Inflection-Aware Search · `[both, P0]` · Needs 00020 seam
- **Goal:** adopt Kaikki's native `descendants` field (primary) with reverse-lookup fallback; deterministic+significant cap; consistent normalization; inflected-form→lemma + case-insensitive search. Folds audit **R3/R4/R6/R7**.
- **Verify FIRST (gating unknown):** `db.words.countDocuments({descendants:{$exists:true,$ne:[]}})` and same for `forms`. If coverage is low, ship value via the fixed fallback path; the audit figures are code-derived.
- **Key files:** `services/tree_builder.py` (`find_descendants` — add the sort; `_build_ancestor_chain`), `template_parser.py` (`normalize_word` both sides), `routers/search.py` + `words.py` (forms/`form_of`/`alt_of` + case-insensitive via the built-but-unused text index), maybe `backend/etl/` to parse `descendants`, new fixtures.
- **Gotchas:** the **non-deterministic `.limit(50)`** and the **raw-vs-normalized descendant match** are the two flagship bugs — they live *inside* the query method, so they're only catchable at **Tier-0 (`normalize_word` direct) / Tier-1 (real Mongo)**, never behind the Tier-2 fake. The "sort-by-out-degree" cap has no port method yet → add `count_descendants` or `@pytest.mark.discovery` it. None of the 11 existing SPC-00013 fixtures hit the 50-cap (max 40 on *hound*) → add a deliberately cap-hitting fixture.

### SPC-00015 — Doublets & Shared-Root Pairs · `[both, P1, flagship]` · Needs 00014
- **Goal:** surface same-language words from a shared ancestor via different routes (*shirt/skirt*, *salt/salary*). Detect from shared ancestry (NOT phonetics). Detail-panel "Doublets" section + optional graph highlight.
- **Key files:** new detection logic in `services/` (consider a precomputed collection à la SPC-00012 if query-time cost is high), a router/endpoint, `frontend/public/js/graph.js` (`showDetail`).
- **Gotcha:** doublets are intra-language and provenance-based; keep them distinct from the existing cross-language `cog` cognate feature.

### SPC-00016 — Sound-Change Correspondences · `[linguist-lead, P1]` · Needs 00002 + 00014
- **Goal:** align IPA between adjacent inheritance steps and highlight what changed (*p→f*). Visualization of observed differences — **not** a sound-law engine.
- **Key files:** backend alignment over existing `phonetic.tokens` (reuse the normalized-Levenshtein backbone from `phonetic_similarity.py`), `frontend/public/js/graph.js` detail panel + optional edge label.
- **Gotcha:** degrade gracefully when one side lacks IPA; rule labels (Grimm) stay optional + clearly heuristic.

### SPC-00017 — Graph Export & Interoperability · `[linguist + hobbyist, P1]` · Ready
- **Goal:** image export (PNG via `canvas.toBlob`, SVG where feasible) + structured export (GraphML/GEXF, Newick/Nexus, CLDF, JSON) behind an "Export ▾" menu.
- **Key files:** `frontend/public/js/graph.js` (canvas export + menu), new backend `GET /api/etymology/{word}/export?format=…` with serializers, `index.html`.
- **Gotcha:** Newick is the **inheritance spanning tree only** (the full graph has cognate/borrowing cross-links and isn't a tree) — label it so.

### SPC-00018 — Guided Discovery · `[hobbyist, P1]` · Partly ready
- **Goal:** word of the day (date-seeded), random/"surprise me" (quality-filtered), curated tours, data-driven "did you know" cards.
- **Key files:** new `GET /api/discovery/*` endpoints + a small curated store (JSON or a `discovery` collection), `frontend/public/js/app.js` + `index.html`.
- **Gotcha:** WOTD/random/tours are independent and can start now; **"did you know" depends on SPC-00015's** doublets engine. Keep it accountless/local (no tracking), consistent with the app's ethos.

### SPC-00019 — Accessibility & UX Baseline · `[both, P1]` · Ready
- **Goal:** keyboard nav for autocomplete; ARIA/`aria-live`; restored focus rings; colorblind-safe + redundant (non-color) family encoding; loading/error/empty states; mobile `@media` reflow; cheap nav wins (breadcrumb history, click-legend-to-isolate, filter-by-family, copy-share-link). Closes audit **R8**.
- **Key files:** `frontend/public/index.html`, `search.js`, `app.js`, `graph.js` (legend), `css/style.css`.
- **Gotchas:** 21 families exceed any palette's distinguishability → encoding must be **redundant** (label/pattern), not just a new palette. Modifies SPC-00003 (adds copy-link + history trail). The `graph.js` god-file refactor and the duplicated trackpad/touch consolidation are **out of scope** here (tracked as structural debt; deprecated SPC-00007 has the note) — but consolidating the duplicated handlers is fair game if you're already in them.

---

## 5. Already done — do NOT redo

- **G6 spec rot (audit R1):** `00005` reclaimed as `deprecated`; `00006`–`00010` marked `deprecated`; `CLAUDE.md` canonical-example pointer repaired. No code existed; nothing to implement.
- **Doc drift (R5):** `CLAUDE.md` "Current Status" refreshed; `FEATURES.md` test counts fixed.
- Pre-existing missing decision-logs on `00001`–`00004`/`00006` are **noted** in the audit (§A2), not back-filled (fabricating retroactive rationale would be dishonest). Leave as-is unless a human wants them reconstructed.

---

## 6. Definition of done (per package)

- Spec status flipped `draft → implemented`; `docs/FEATURES.md` updated **before** committing (house rule).
- `make lint` clean; new logic covered per **SPC-00020**'s tier model (Tier-0 for pure logic; Tier-2 for orchestration; mark anything needing real Mongo `requires_docker`). No test monkeypatches a module global.
- Commits: `SPC-NNNNN: Description`. PRs follow `code_review/GUIDELINES.md` — DA opens with the structured description, RA reviews, comments prefixed `**[DA]**:` / `**[RA]**:`.
- Bidirectional spec traceability preserved (`Modifies`/`Modified-by`) if your change touches another spec's behavior.

---

## 7. Open questions for the dispatcher / human

- **Approve gate?** Flip the `draft` specs to `approved` after a human skim, or let workers proceed from `draft`?
- **SPC-00020 Step 4 (the port) scope:** land it in the same PR as Steps 1-3, or as a fast-follow once the acceptance net is green? (Spec recommends fast-follow behind the net.)
- **Data coverage:** someone should run the SPC-00014 `countDocuments` checks against a loaded DB and drop the real numbers into `docs/AUDIT-2026-06.md` (currently labeled code-derived).
- The unmerged `origin/claude/api-*-tests` branches look aimed at R2 — worth a look before writing API tests from scratch (noted in the audit's git-history finding).
