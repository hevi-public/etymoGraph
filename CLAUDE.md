# Etymology Explorer

A local, Dockerized tool for exploring word etymologies with interactive graph visualization.

## Stack

- **Database**: MongoDB (flexible schema for Kaikki JSONL)
- **Backend**: Python FastAPI (async, auto-docs)
- **Frontend**: Vanilla JS + vis.js (no build step)
- **Data**: Kaikki.org English Wiktionary dump
- **Orchestration**: Docker Compose

## Project Structure

```
etymology-explorer/
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
│   │       ├── etymology.py # GET /api/etymology/{word}/chain
│   │       └── search.py    # GET /api/search?q=
│   └── etl/
│       └── load.py          # Load Kaikki into MongoDB
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── public/
│       ├── index.html
│       ├── css/style.css
│       └── js/
│           ├── app.js       # Main application
│           ├── graph.js     # vis.js graph logic
│           ├── search.js    # Search functionality
│           └── api.js       # API client
├── data/                    # Gitignored
│   └── raw/                 # Downloaded dumps
└── scripts/
    └── download-data.sh
```

## Commands

```bash
make setup    # First time: build, download data, load into MongoDB
make run      # Start all services
make stop     # Stop all services
make logs     # View logs
make clean    # Remove data and containers
```

## URLs (when running)

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MongoDB: localhost:27017

## Current Status

**Phase**: P0 - Prototype
**Last completed**: None (starting fresh)
**Next task**: P0.1 - Basic Docker + vis.js setup

## Implementation Plan

See `docs/IMPLEMENTATION_PLAN.md` for detailed task breakdowns.

## Conventions

### Code Style
- Python: Use async/await with FastAPI
- JavaScript: Vanilla ES6+, no frameworks
- Use meaningful variable names
- Add comments for non-obvious logic

### Git Commits
- Format: `[TASK_ID]: Description`
- Example: `P0.1: Basic Docker + vis.js setup`
- Commit after each completed task

### API Design
- All endpoints under `/api/`
- Return JSON
- Use proper HTTP status codes (200, 404, 500)
- Include CORS headers for frontend

### vis.js Graph
- Nodes: `{ id: "word:lang", label: "word", language: "lang" }`
- Edges: `{ from: "...", to: "...", label: "inherited|borrowed|derived" }`
- Hierarchical layout (ancestors above)

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
