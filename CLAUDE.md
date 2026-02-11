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
│       └── load.py          # Load Kaikki into MongoDB
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
│   │       └── api.js       # API client
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

**Phase**: MVP complete + Phase 2 in progress
**Last completed**: G6 renderer fixes — physics animation, force spacing, trackpad interaction (SPC-00006)
**Next task**: Remaining Phase 2 nice-to-haves (see docs/FEATURES.md for status)

**Recent**: Implemented shareable links (SPC-00003) with:
- `router.js` — view-scoped URL parameter registry with History API integration
- URL reflects current state (word, language, filters, view, concept map settings)
- Browser back/forward navigates between word searches and view switches
- Page refresh restores full state from URL
- Vitest unit tests (17 tests) + Playwright E2E tests (10 tests)

## Documentation

- `README.md` — User-facing guide: what the app does, feature overview, walkthrough examples, setup instructions.
- `docs/FEATURES.md` — Detailed feature documentation, API reference, implementation status, known limitations. **Keep this up to date when adding or changing features.**
- `docs/IMPLEMENTATION_PLAN.md` — Original implementation plan with task breakdowns.
- `docs/CODING_STANDARDS.md` — Python and JavaScript coding standards with enforcement details.
- `specs/` — Feature specifications. **Read below for conventions.**

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

See `specs/00005-g6-experimental-renderer/decision-log.md` for the canonical example.

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
