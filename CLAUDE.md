# Etymology Explorer

A local, Dockerized tool for exploring word etymologies with interactive graph visualization.

## Stack

- **Database**: MongoDB (flexible schema for Kaikki JSONL)
- **Backend**: Python FastAPI (async, auto-docs)
- **Frontend**: Vanilla JS + vis.js (no build step)
- **Data**: Kaikki.org full multilingual Wiktionary dump (10.4M documents)
- **Orchestration**: Docker Compose

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

## URLs (when running)

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MongoDB: localhost:27017

## Current Status

**Phase**: MVP complete + Phase 2 in progress
**Last completed**: Etymology link mode toggle (in-app / Wiktionary) for chain items, prose, and cognates
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

### Git Commits
- Format: `[TASK_ID]: Description`
- Example: `P0.1: Basic Docker + vis.js setup`
- **ALWAYS update `docs/FEATURES.md` before committing any feature or behavior change**
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
- Edges: `{ from: "...", to: "...", label: "inh|bor|der|cog" }`
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
- `sounds[].ipa` — pronunciation

Etymology template types:
- `inh` = inherited from (direct ancestor)
- `bor` = borrowed from (loanword)
- `der` = derived from
- `cog` = cognate (related, not ancestor)

Important: Kaikki stores the **full** ancestry chain on each word (not just the immediate parent). The tree builder uses only the first ancestry template to determine the direct parent.

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
