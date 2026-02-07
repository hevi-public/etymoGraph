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
│   └── public/
│       ├── index.html
│       ├── css/style.css
│       └── js/
│           ├── app.js       # Main application, filter wiring
│           ├── graph.js     # vis.js graph, zoom, trackpad, detail panel
│           ├── search.js    # Search autocomplete
│           └── api.js       # API client
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
**Last completed**: Expanded language family colors (9→20 families) with dynamic legend
**Next task**: Remaining Phase 2 nice-to-haves (see docs/FEATURES.md for status)

## Documentation

- `docs/FEATURES.md` — Detailed feature documentation, API reference, implementation status, known limitations. **Keep this up to date when adding or changing features.**
- `docs/IMPLEMENTATION_PLAN.md` — Original implementation plan with task breakdowns.
- `README.md` — User-facing setup and usage guide.

## Conventions

### Code Style
- Python: Use async/await with FastAPI
- JavaScript: Vanilla ES6+, no frameworks
- Use meaningful variable names
- Add comments for non-obvious logic
- Code style should follow general Clean Code principles with Functional Paradigm style. Such as: heavy use of small pure-functions, that are expressive in themselves (don't make a function call of an elementary operation for example). Consider code readability and understandability, maintainability from both human and LLM perspective
- **Extract logic into small functions**: When implementing new features or modifying code, proactively separate logic into smaller, focused functions. This improves readability, testability, and makes the codebase easier to understand for both humans and LLMs.
- **Add contextual comments**: When making changes, add brief comments explaining the *why* behind non-obvious decisions or the context that led to the change. These comments help future readers (including future LLM sessions) understand the reasoning without needing to re-derive it.

### Git Commits
- Format: `[TASK_ID]: Description`
- Example: `P0.1: Basic Docker + vis.js setup`
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
