# Etymology Explorer

Interactive graph visualization of word etymologies, powered by Wiktionary data from [Kaikki.org](https://kaikki.org/).

Trace words back through history — see how "wine" traveled from Proto-Indo-European through Latin, Old English, and into modern English.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Git
- (Optional) [Claude Code](https://code.claude.com/) — for MCP-enhanced development experience

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

## Development with Claude Code

This project includes MCP (Model Context Protocol) server configurations for enhanced development with [Claude Code](https://code.claude.com/):

- **MongoDB MCP**: Direct database queries and data inspection
- **Playwright MCP**: Automated frontend testing and screenshots
- **GitHub MCP**: Enhanced PR and issue management

MCP servers are automatically configured via `.mcp.json`. Start a new Claude Code session to load the tools, then try:
- "List collections in the etymology database"
- "Test the search functionality on localhost:8080"
- "Take a screenshot of the graph"

See `CLAUDE.md` for detailed MCP documentation.

## Troubleshooting

**Docker not running**: Start Docker Desktop before running `init.sh` or `docker compose up`.

**Port conflict on 8080**: Another service is using the port. Stop it or change the port in `docker-compose.yml`.

**Blank page**: Check browser console for errors. Ensure vis.js CDN is accessible.
