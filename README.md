# Etymology Explorer

Interactive graph visualization of word etymologies, powered by Wiktionary data from [Kaikki.org](https://kaikki.org/).

Trace words back through history — see how "wine" traveled from Proto-Indo-European through Latin, Old English, and into modern English.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git

## Quick Start

```bash
git clone <repo-url> && cd etymo_graph
./scripts/init.sh       # Check prereqs, create dirs, build images
docker compose up -d    # Start services
open http://localhost:8080
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:8080 | Graph visualization UI |
| Backend API | http://localhost:8000 | FastAPI (future) |
| API Docs | http://localhost:8000/docs | Swagger UI (future) |
| MongoDB | localhost:27017 | Database (future) |

## Project Structure

```
├── docker-compose.yml       # Service orchestration
├── frontend/
│   ├── Dockerfile           # nginx:alpine
│   ├── nginx.conf           # Static file serving
│   └── public/              # HTML, CSS, JS
│       ├── index.html
│       ├── css/style.css
│       └── js/graph.js      # vis.js etymology graph
├── backend/                 # FastAPI (Phase 1)
├── data/                    # Kaikki dumps (gitignored)
├── scripts/
│   └── init.sh              # Project setup
└── docs/
    └── IMPLEMENTATION_PLAN.md
```

## Current Status

**Phase 0 — Prototype**: Hardcoded etymology graph for "wine" rendered with vis.js. No database or API yet.

See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the full roadmap.

## Tech Stack

- **vis.js** — Interactive network graph visualization
- **nginx** — Static file serving
- **Docker Compose** — Orchestration
- **MongoDB** — Document store for Kaikki data (Phase 1)
- **FastAPI** — Python async API (Phase 1)

## Troubleshooting

**Docker not running**: Start Docker Desktop before running `init.sh` or `docker compose up`.

**Port conflict on 8080**: Another service is using the port. Stop it or change the port in `docker-compose.yml`.

**Blank page**: Check browser console for errors. Ensure vis.js CDN is accessible.
