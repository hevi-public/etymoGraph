# Etymology Explorer

A local, Dockerized tool for exploring word etymologies with interactive graph visualization.

## Stack

- **Database**: MongoDB (flexible schema for Kaikki JSONL)
- **Backend**: Python FastAPI (async, auto-docs)
- **Frontend**: Vanilla JS + vis.js (no build step)
- **Data**: Kaikki.org full multilingual Wiktionary dump (10.4M documents)
- **Orchestration**: Docker Compose
- **MCP Servers**: MongoDB, Playwright, GitHub (for Claude Code integration)

## Project Structure

```
etymo_graph/
├── docker-compose.yml
├── Makefile
├── .env.example
├── vitest.config.js          # Vitest unit test config (jsdom)
├── playwright.config.js      # Playwright E2E test config
├── eslint.config.js          # ESLint flat config (app + test blocks)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── config.py        # Settings
│   │   ├── database.py      # MongoDB connection
│   │   └── routers/
│   │       ├── words.py     # GET /api/words/{word}
│   │       ├── etymology.py # GET /api/etymology/{word}/chain + /tree
│   │       └── search.py    # GET /api/search?q=
│   └── etl/
│       ├── load.py          # Load Kaikki into MongoDB
│       └── precompute_edges.py  # Precompute compound/affix edges
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf            # Static files + /api/ proxy to backend
│   ├── public/
│   │   ├── index.html
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── app.js       # Main application, filter wiring, router init
│   │       ├── router.js    # URL router — view-scoped params, History API
│   │       ├── graph.js     # vis.js graph, zoom, trackpad, detail panel
│   │       ├── search.js    # Search autocomplete
│   │       ├── concept-map.js # Concept map view
│   │       ├── api.js       # API client
│   │       └── layout-stream.js # SSE layout-stream client + rAF tween (SPC-00021)
│   └── tests/
│       └── router.test.js   # Vitest unit tests for router.js
├── tests/
│   └── e2e/
│       ├── helpers.js        # Shared E2E utilities
│       └── shareable-links.spec.js  # Playwright E2E tests
├── specs/                   # Feature specifications (see Specs section below)
├── data/                    # Gitignored
│   └── raw/                 # Downloaded dumps
├── scripts/
│   ├── init.sh              # Project setup
│   └── download-data.sh     # Download Kaikki dump
└── docs/
    ├── IMPLEMENTATION_PLAN.md
    └── FEATURES.md           # Detailed feature documentation
```

## Commands

```bash
make setup    # First time: build, download data, load into MongoDB
make run      # Start all services
make stop     # Stop all services
make update   # Force re-download data + reload
make logs     # View logs
make clean    # Remove data and containers

# Precomputation (run after make load)
make precompute-edges     # Precompute compound/affix etymology edges

# Testing
make test-frontend  # Run Vitest unit tests (router, etc.)
make test-e2e       # Run Playwright E2E tests (requires make run)
make test-all       # Run all tests (pytest + Vitest + Playwright)
```

## MCP Servers (Claude Code Integration)

This project uses Model Context Protocol (MCP) servers to enhance Claude Code's capabilities:

### Configured MCP Servers

**MongoDB MCP** (`mongodb-mcp-server`)
- Direct database queries without docker exec commands
- Connected to: `mongodb://localhost:27017` (database: `etymology`)
- Usage: "List collections", "Query for words with uncertain etymologies", "Count entries by language"
- Requires: Docker containers running (`make run`)

**Playwright MCP** (`@executeautomation/playwright-mcp-server`)
- Browser automation for testing the frontend
- Usage: "Test search on localhost:8080", "Take screenshot of graph", "Click on a node"
- Can verify graph rendering, interactions, and visual regressions
- **Screenshots**: ALWAYS save to `docs/screenshots/` (within the working directory). NEVER save to ~/Downloads or any path outside the project. Use `savePng: true` with `downloadsDir: "docs/screenshots/"` or equivalent.

**GitHub MCP** (HTTP)
- Enhanced PR and issue management beyond `gh` CLI
- Requires: Authentication via `/mcp` command in Claude Code
- Usage: Advanced PR reviews, issue tracking, repository insights

### Setup & Configuration

MCP servers are configured in `.mcp.json` (project-scoped, committed to repo). They are automatically loaded when Claude Code starts.

**First-time setup:**
1. Start a new Claude Code session in this project
2. MCP tools will be automatically available
3. For GitHub MCP: Run `/mcp` to authenticate via browser

**Verifying MCP status:**
```bash
claude mcp list    # Shows all configured servers and connection status
claude mcp get mongodb  # Shows details for specific server
```

**Important:** Always use MCP tools instead of bash workarounds:
- ❌ `docker exec etymograph-mongodb-1 mongosh ...`
- ✅ Ask Claude: "List collections in the etymology database"

### Troubleshooting MCP

**"Failed to connect" for MongoDB:**
- Ensure Docker containers are running: `make run`
- Check MongoDB is healthy: `docker ps` (should show "healthy" status)

**MCP tools not appearing:**
- Restart Claude Code session (MCP tools load at startup)
- Check connection: `claude mcp list`

**GitHub authentication:**
- Use `/mcp` command in Claude Code
- Follow browser OAuth flow

### MongoDB MCP Best Practices

**Querying efficiently:**
- Large documents (100KB+) require projections to avoid context overflow
- Use `aggregate` with `$project` instead of `find` for selective field retrieval
- Example: `[{"$match": {...}}, {"$limit": 1}, {"$project": {"word": 1, "sounds": {"$slice": ["$sounds", 2]}}}]`
- Set `responseBytesLimit` parameter to cap response size (default: 1MB, max: server-configured limit)

**Query patterns:**
- Existence checks: `{"sounds.ipa": {"$exists": true}}`
- Nested field queries: `{"etymology_templates.name": "inh"}`
- Use `count` for statistics before fetching full documents
- Save large results to temp files when analyzing data patterns

## URLs (when running)

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MongoDB: localhost:27017

## Current Status

**Phase**: Core product complete (vis.js etymology graph + phonetic concept map); SPC-00021
(server-side layout + SSE) fully implemented — all phases done, spec status `implemented`
**Last completed**: SPC-00021 Phase 5 — `layoutMode` default flipped to `server` (client stays the
explicit/fallback path), §10 server cold/warm table measured live (`make bench-layout-server`:
cheese era 0.42 s cold / 0.29 s warm vs client-physics *never stabilizing*; every graph at target
scale within targets; live cupboard grew to 1,028 nodes and its 6.98 s cold solve belongs to the
deferred §11 Barnes-Hut follow-up). Two defects closed on the way: (1) the RA-flagged server-mode
multi-concept tint loss — `_build_concept_job` now tags per-word `concepts` membership
(copy-on-insert; resolver cache never mutated), `concept-map.js` normalizes it onto `_concepts`
via pure `normalizeConceptMembership`; (2) **a concept-layout blow-up caught by the Phase 5
acceptance screenshots** — the engine ran the FA2 repulsion law (∝ degree/d) for all layouts, but
concept's G=-8000 is barnesHut-calibrated (∝ 1/d², no degree), so every concept solve expanded to
a clamp-limited ±7.7–11.4k px square; fixed with `SolverParams.repulsion_law` (barnesHut law pinned
from vis-network v9.1.9 source), `LAYOUT_ALGO_VERSION` → `"3"`, red-first regression
`test_concept_solve_extent_stays_at_display_scale`. Acceptance evidence: side-by-side screenshots
`docs/screenshots/spc00021-p5-*.png`, `curl -N` incremental frames through nginx, full E2E green
(22 pass; a latent popover bug in `server-layout.spec.js`'s slider test fixed — first live run of
the suite since the merge), backend 168 pass, Vitest 68 pass.
**Next task**: SPC-00021 post-merge follow-ups (spec §9 gaps: SSE cadence-policy test,
`tests/fixtures/layout/final/` characterization snapshots; hardware-flaky 1.5 s cupboard budget in
`test_layout_perf.py`; concept re-solve rebuilds the vis.Network instead of in-place edge swap;
sticky `?layoutMode=` localStorage rewrite; `chemistry.json` live regen; `find_descendants`
derived-alias FakeWordsCollection test) — or start a roadmap spec (SPC-00014–00020).

**Recent**:
- SPC-00021 Phase 5 (2026-07-10): described above. Measurement harness gained
  `LAYOUT_BASELINE_MODE=server` (settle := `final` applied + 300 ms tween, cold = run 1 on an
  empty `layouts` collection, warm = median of runs 2–3) + `make bench-layout-server`. Details in
  spec §10 footnotes 2–3 + decision-log addendum.
- SPC-00021 Phase 0d (2026-07-10): baseline harness + measured table (spec §10, decision-log
  addendum). Probes install via `page.addInitScript` (an accessor on `window.__etymoNetwork`; the
  concept map needs an rAF poller instead — its `conceptNetwork` was a top-level `let`, so the
  `window.conceptNetwork` hook the E2E helpers assert on had never actually existed; since fixed
  in PR #20 — `concept-map.js` now sets `window.conceptNetwork` explicitly). Measured against
  SPC-00013 fixture trees (`LAYOUT_BASELINE_FIXTURES=1`) because the local MongoDB had lost its
  `etymology.words` collection at measurement time (since restored via full reload; the
  concept-map baseline column is deferred to a follow-up live run).
- SPC-00021 Phase 3+4 (2026-07-05): frontend integration described above. Flag is read URL >
  localStorage > default (`client`); it is intentionally NOT a view-scoped router param (that would
  reset on view switch and break the router's `.toEqual` unit tests), so an explicit `?layoutMode=`
  is persisted to localStorage on load to survive URL normalization. Known gap carried forward:
  server-mode multi-concept nodes render with base language color (the server merge drops per-word
  concept membership) — documented in `docs/FEATURES.md`. E2E requires the live stack, so this phase
  was verified via lint (0 errors) + the full Vitest suite; browser-level assertions ship as
  `server-layout.spec.js` for `make test-e2e`.
- fix (2026-07-05): closed the `"derived"`-alias gap flagged below. `ANCESTRY_TYPES` didn't
  recognize Wiktionary's spelled-out `derived` template as an alias of `der` (same relationship,
  just not abbreviated — confirmed via Wiktionary's own template docs), so chemistry's
  Latin/Arabic/Greek ancestry stayed invisible to `/chain` and to `/tree`'s descendant search.
  Added `ANCESTRY_TYPE_ALIASES`/`expand_ancestry_types()` in template_parser.py (mirrors the
  existing `suf`/`suffix` pattern); wired into `TreeBuilder.find_descendants`'s Mongo query and
  `etymology_classifier`'s ancestry-exclusion set. `chemistry.json`'s `system_output.chain` and the
  ancestor-chain portion of `tree_inh_bor_der_cog` are regenerated; further descendant/compound
  fan-out from the newly-visible ancestor nodes still needs a live-stack fixture regen to confirm.
- SPC-00021 Phase 2 (2026-07-05): endpoints + SSE + `layouts` cache + nginx + acceptance/
  characterization tests. Refactored `etymology.py`/`concept_map.py` to extract shared
  `build_tree`/`resolve_concept_words` so the layout endpoints reuse the exact topology path (no
  drift). Extended `FakeWordsCollection` with `$or`/`$ne`/`$regex` + `replace_one` for concept
  acceptance + cache tests; added the missing `concept_resolver._concept_cache` autouse reset.
  Backend suite: 117 pass (the 2 `slow` perf-budget tests are hardware-sensitive and flake on
  slow/BLAS-less numpy — unrelated to Phase 2).
- SPC-00021 follow-ups merged (2026-07-05): two background tasks spawned from the Phase 0+1 work
  landed as separate PRs (#14, #15) and were reunified onto this branch. #14 fixes the
  `find_descendants` reverse-edge bug described below (ancestor→descendant direction restored,
  matching `_build_ancestor_chain`); #15 adds a merge-preserving mode to
  `collect_wiktionary_examples.py` (no longer clobbers hand-curated `known_gaps`/notes on
  `--force`) and regenerates all 11 fixtures incorporating both fixes. `docs/FEATURES.md`'s
  now-obsolete "duplicate reverse edges" limitation entry was removed. While resolving a stale
  review note on `chemistry.json`, found and separately flagged another gap: `ANCESTRY_TYPES`
  doesn't recognize `"derived"` as an alias of `"der"`, so some words' ancestor chains (chemistry's
  Latin/Arabic/Greek ancestry, specifically) are invisible to `/chain` even though the compound-edge
  path (`/tree`'s `component` edges) already works correctly.
- SPC-00021 Phase 0+1 (2026-07-05): `find_descendants` deterministic sort (fixture regen deferred —
  the collector script clobbers hand-curated `known_gaps`/notes on `--force`, needs a
  merge-preserving mode first — since fixed, see above); SPC-00020 Steps 1–3 DI seam (lifespan
  Motor client + Depends); `FakeWordsCollection` + real TreeBuilder tests; JS layout goldens
  (`frontend/tests/layout-goldens.test.js`, fixed two latent Vitest/jsdom harness bugs along the
  way — missing `localStorage`, silently-dropped `eval()`-scope globals); the full numpy layout
  engine with formulas pinned directly from vis-network's own source (not just its options docs).
  Cupboard-scale (940 nodes) solves in ~1.3s, within budget, after reformulating the O(n²)
  repulsion as a BLAS matmul (the first cut missed the 1.5s budget by 4x). Found and separately
  flagged (fixed above in #14): a pre-existing bug where `find_descendants` adds
  ancestor/descendant edges in the reverse direction from `_build_ancestor_chain`, producing
  duplicate reverse edges in most multi-hop etymology chains.
- SPC-00021 (2026-07-04, approved): move graph layout from vis.js client physics to a backend
  numpy solver streaming states over SSE; frontend tweens between frames with physics disabled;
  client physics kept as `layoutMode=client` fallback. Modifies SPC-00004/00002; pulls SPC-00014's
  R3 determinism slice and SPC-00020's Steps 1–3 forward.
- Feature audit `docs/AUDIT-2026-06.md` (2026-06-27): full audit + prioritized, audience-tagged
  roadmap. Drafted specs SPC-00014–00019; reclaimed SPC-00005 and deprecated the abandoned G6
  renderer line (SPC-00005–00010 — no G6 code ever merged; vis.js is the sole renderer).
- SPC-00011 (chain normalization + polysemy), SPC-00012 (precomputed compound edges), SPC-00013
  (fixture/characterization test machinery) all shipped since SPC-00003/00004.
- **Implemented specs:** 00001–00004, 00011, 00012, 00013 (Phases 1–3), 00021 (server-side layout
  + SSE). **Deprecated:** 00005–00010 (G6). **Draft (roadmap):** 00014–00020.
  SPC-00020 (Tiered Testing Architecture) applies the `bdd-tiered-testing` skill to this stack and
  is the home for the audit's R2 (untested core engine).

## Documentation

- `README.md` — User-facing guide: what the app does, feature overview, walkthrough examples, setup instructions.
- `docs/FEATURES.md` — Detailed feature documentation, API reference, implementation status, known limitations. **Keep this up to date when adding or changing features.**
- `docs/IMPLEMENTATION_PLAN.md` — Original implementation plan with task breakdowns.
- `docs/CODING_STANDARDS.md` — Python and JavaScript coding standards with enforcement details.
- `specs/` — Feature specifications. **Read below for conventions.**

## Claude Code Skills (`.claude/skills/`)

Project-local skills, auto-loaded by Claude Code. Consult the matching skill **before** working in
its area. The four testing/stack skills are adapted from the HAIP project (hevi-public/haip) for
this Python/FastAPI/Motor + vanilla-JS stack:

- `bdd-tiered-testing` — the testing philosophy: tiers, the single IO seam, discovery mode,
  log-as-contract, de-flaking. Companion to SPC-00020. Read before writing any test.
- `fastapi-acceptance-bdd` — hermetic acceptance wiring (httpx ASGITransport, dependency_overrides,
  seeded fakes, SSE contract tests, rail tests) + the Playwright E2E layer.
- `mongodb-motor-data` — the Mongo/Motor layer: seam/DI, query gotchas (sort-before-limit,
  collation, projections), indexes, bounded recursion, precompute-collection pattern, test-DB tiers.
- `vanilla-js-frontend` — no-build-step frontend conventions: script load order, pure-core/DOM-glue
  split, Vitest eval harness, stable test hooks, asset pinning, SSE/Worker patterns.
- `vis-docs` — vis.js Network & DataSet API reference for the graph views.

## Specs

Every feature or significant change must have a spec before implementation. Specs live in `specs/` as numbered folders.

### Structure

```
specs/
  00001-connection-based-edges/
    spec.md              # The specification (always named spec.md)
    decision-log.md      # How and why decisions were made
    (optional resources)  # Diagrams, mockups, sample data, etc.
  00002-phonetic-similarity-concept-map/
    spec.md
    decision-log.md
  00003-shareable-links-url-routing/
    spec.md
    decision-log.md
```

### Naming Convention

- **Folder**: `NNNNN-short-kebab-description/` — 5-digit zero-padded incrementing prefix
- **Main file**: always `spec.md` inside the folder
- **Resources**: any supporting files (diagrams, JSON examples, test fixtures) sit alongside `spec.md`
- **Next number**: look at the highest existing folder number and increment by 1

### Decision Log

Every spec folder **must** include a `decision-log.md` alongside `spec.md`. The decision log documents the conversation journey from initial question to final decision — capturing the *why* behind the spec, not the *what* (that's `spec.md`'s job).

**Required sections:**

1. **Starting Question** — what prompted the investigation or feature
2. **Alternatives Considered** — options evaluated, with pros/cons for each
3. **Decision & Rationale** — what was chosen and why alternatives were eliminated
4. **Participants** — who contributed to the decision (human, agents, roles)

See `specs/00012-precompute-compound-edges/decision-log.md` for the canonical example.

### Spec Header

Every `spec.md` starts with this header:

```markdown
# SPC-NNNNN: Title

| Field | Value |
|---|---|
| **Status** | draft / approved / implemented / deprecated |
| **Created** | YYYY-MM-DD |
| **Modifies** | SPC-NNNNN (brief reason), or — if none |
| **Modified-by** | SPC-NNNNN (brief reason), or — if none |
```

**Status values:**
- `draft` — being written, not ready for implementation
- `approved` — reviewed and ready for implementation
- `implemented` — code has been written and merged
- `deprecated` — superseded by a later spec

### Cross-Referencing

When a new spec modifies behavior defined in an earlier spec:

1. **New spec** gets `Modifies: SPC-NNNNN (brief reason)` in its header
2. **Old spec** gets `Modified-by: SPC-NNNNN (brief reason)` appended to its header
3. **Commit messages** reference the spec ID (see Git Commits below)

This gives bidirectional traceability: from any spec you can see what it changed and what later changed it. `git log --grep="SPC-00003"` finds all commits related to a spec.

### When to Create a Spec

- New features (UI views, API endpoints, data pipeline changes)
- Significant behavioral changes to existing features
- Architecture or design decisions with multiple approaches considered
- NOT needed for: bug fixes, typo corrections, dependency updates, minor refactors

## Conventions

### Code Style

**Follow the comprehensive coding standards defined in `docs/CODING_STANDARDS.md`.**

**Key principles**:
- Python: Type hints + Google-style docstrings for all functions
- JavaScript: Small pure functions, JSDoc for complex functions
- Extract logic into focused functions (<50 lines ideal)
- Add contextual comments explaining *why*, not *what*
- Error handling at system boundaries only
- No over-engineering — keep it simple

**Enforcement**:
- Pre-commit hooks enforce linting (Ruff for Python, ESLint for JavaScript)
- All new code must pass linting before commit
- Review Agent enforces standards during PR review (MUST level violations)

**Development commands**:
```bash
make setup-dev      # Install linters and pre-commit hooks
make lint           # Run linters
make format         # Format code
make test           # Run Python tests
make test-frontend  # Run Vitest unit tests
make test-e2e       # Run Playwright E2E tests (requires make run)
```

**Migration**: Standards apply to all new code immediately. Existing code is refactored opportunistically when touched (no mass refactoring required).

### Git Commits

- Format: `SPC-NNNNN: Description` when implementing a spec
- Example: `SPC-00003: Add router.js with view-scoped parameter registry`
- Example: `SPC-00003: Wire up popstate handler in app.js`
- For non-spec work (bug fixes, chores): `fix: Description` or `chore: Description`
- **Document first, commit second**: ALWAYS update `docs/FEATURES.md` before committing any feature or behavior change
- Commit after each completed task

### Pull Requests
- Always check for the latest usable PR number before submitting (`gh pr list` or `gh pr view`), to avoid creating duplicates or editing the wrong PR

### API Design
- All endpoints under `/api/`
- Return JSON
- Use proper HTTP status codes (200, 404, 500)
- Nginx proxies `/api/` from frontend (port 8080) to backend (port 8000)

### vis.js Graph
- Nodes: `{ id: "word:lang", label: "word", language: "lang", level: N }`
- Edges: `{ from: "...", to: "...", label: "inh|bor|der|cog|component|mention" }`
- Force-directed layout (forceAtlas2Based), continuously animated
- Etymological root pinned at (0,0) as gravitational center, mass 5 with exponential decay per level
- Negative levels = ancestors, 0 = searched word, positive = descendants
- Distance-based opacity on node selection (100% → 90% → 50% → 10% by hop)
- Clicking a node animates it to viewport center

## Kaikki Data Notes

Key fields in Kaikki entries:
- `word`, `lang`, `pos` — identification
- `etymology_text` — human-readable etymology
- `etymology_templates` — structured relationships (builds the graph)
- `senses[].glosses` — definitions
- `sounds[]` — pronunciation data (see structure below)

### Sounds Field Structure

The `sounds` array contains pronunciation information (available in ~31.7% of entries, 3.3M/10.4M documents):

```json
"sounds": [
  {"enpr": "chēz"},                                    // English pronunciation respelling
  {"ipa": "/t͡ʃiːz/"},                                  // IPA pronunciation
  {"tags": ["General-American"], "ipa": "/t͡ʃiz/"},   // Regional IPA variants
  {"audio": "file.ogg", "ogg_url": "...", "mp3_url": "..."}, // Audio files
  {"rhymes": "-iːz"},                                  // Rhyme pattern
  {"homophone": "qis"}                                 // Homophones
]
```

**Best practices for querying sounds:**
- Use MongoDB aggregation with `$project` to limit fields when querying documents with sounds (entries can be 100KB+)
- Query pattern: `{"sounds.ipa": {"$exists": true}}` to find entries with IPA data
- Use `responseBytesLimit` parameter in MCP queries to prevent context overflow

Etymology template types (ancestry):
- `inh` = inherited from (direct ancestor in same language lineage)
- `bor` = borrowed from (loanword from another language)
- `der` = derived from (general derivation)
- `cog` = cognate (related word from same root, not ancestor)

Etymology template types (mentions, used when no ancestry exists):
- `af`, `affix`, `suffix`, `prefix`, `compound`, `blend` = word formation templates showing morphological components
- `m`, `m+`, `l` = mention/link templates referencing related words

Important: Kaikki stores the **full** ancestry chain on each word (not just the immediate parent). The tree builder uses only the first ancestry template to determine the direct parent. For words without ancestry (often uncertain/disputed etymologies), the tree builder falls back to `af`/`m` templates to show related words.

## Code Review Process

Reviews happen through GitHub Pull Requests, not local files. See `code_review/GUIDELINES.md` for the full process.

**Agent identification:** All PR comments must be prefixed with `**[DA]**:` or `**[RA]**:` since everything appears under the human's GitHub account. Each agent determines its role from context (writing code = DA, reviewing = RA).

**Quick reference:**
1. **Developer Agent (DA)** opens a PR with structured description (what changed, files, how to verify, concerns)
2. **Review Agent (RA)** reviews the PR using `gh` CLI — inline comments + summary review with MUST/SHOULD/CONSIDER findings
3. **Developer Agent** responds to each finding (accept/counter/challenge), pushes fixes
4. **Review Agent** re-reviews and approves or requests changes
5. **Human** is notified at each step with the PR URL and what to do next

Key files:
- `code_review/GUIDELINES.md` — Full review process, severity levels, tiebreaking rules
- `code_review/REVIEW_TEMPLATE.md` — Comment format reference for the Review Agent
- `.github/PULL_REQUEST_TEMPLATE.md` — PR description template

## Working Principles

- **Automate everything**: Every repeatable action should be scriptable. Use `scripts/`, `Makefile`, and Docker Compose so nothing requires manual steps.
- **Document everything important**: Keep README, CLAUDE.md, FEATURES.md, and IMPLEMENTATION_PLAN.md up to date. Update current status after completing tasks. Add troubleshooting notes when issues are encountered.
- **Update feature docs**: When adding or changing features, always update `docs/FEATURES.md` with the current state, and note any new known limitations.
- **Spec before code**: Every significant feature or change gets a spec in `specs/` before implementation begins. This ensures design decisions are captured and traceable.
