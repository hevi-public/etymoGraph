# Etymology Database: Local Implementation Plan

## Overview

This plan outlines the implementation of a local, Dockerized etymology database with graph visualization. The project is designed for personal use on Mac, with optional static export to GitHub Pages.

**Implementer**: Claude Code
**Environment**: Local Mac + Docker
**Data Source**: Kaikki.org Wiktionary dump
**Sharing**: Static exports to GitHub Pages

---

## Tech Stack

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Frontend   │    │   Backend    │    │   Database   │       │
│  │   (nginx)    │◄──►│  (FastAPI)   │◄──►│  (MongoDB)   │       │
│  │              │    │              │    │              │       │
│  │  - vis.js    │    │  - Python    │    │  - Kaikki    │       │
│  │  - Search    │    │  - REST API  │    │    JSONL     │       │
│  │  - Graph UI  │    │  - PyMongo   │    │  - Flexible  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│        :8080             :8000              :27017               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Stack Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Database** | MongoDB | Direct JSONL import; flexible schema; explore first, optimize later |
| **Data Source** | Kaikki dump | Full Wiktionary: definitions, pronunciations, etymology; familiar content |
| **Graph Visualization** | vis.js | Simpler than D3; interactive out-of-box; good network graph support |
| **Backend** | Python FastAPI | Auto-generated docs; async; Claude Code writes it well |
| **Frontend** | Vanilla JS + vis.js | No build step; fast iteration |
| **Orchestration** | Docker Compose | Single command to run everything |

### Why MongoDB for Prototype?

| Benefit | Details |
|---------|---------|
| **Direct import** | `mongoimport --file kaikki.jsonl` — no parsing needed |
| **Flexible schema** | Words have different fields; no migrations |
| **Natural fit** | Kaikki is JSONL; MongoDB stores JSON natively |
| **Explore freely** | Query any nested field without upfront schema design |
| **Easy migration** | Can move to PostgreSQL/Neo4j later if needed |

---

## Project Structure

```
etymology-explorer/
├── docker-compose.yml           # Orchestration
├── .env.example                 # Environment template
├── Makefile                     # Automation commands
├── README.md                    # Setup instructions
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings
│   │   ├── database.py          # MongoDB connection
│   │   └── routers/
│   │       ├── words.py         # Word lookup endpoints
│   │       ├── etymology.py     # Etymology chain endpoints
│   │       └── search.py        # Search endpoints
│   └── etl/
│       ├── __init__.py
│       ├── download.py          # Download Kaikki dump
│       └── load.py              # Load into MongoDB
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── public/
│       ├── index.html           # Main page
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── app.js           # Main application
│           ├── graph.js         # vis.js graph logic
│           ├── search.js        # Search functionality
│           └── api.js           # API client
│
├── data/                        # Persistent volume (gitignored)
│   └── raw/                     # Downloaded dumps
│
└── scripts/
    ├── download-data.sh         # Download Kaikki dump
    └── export-static.sh         # Export to GitHub Pages
```

---

## Kaikki Data Structure

Understanding the data we're working with:

### Sample Kaikki Entry

```json
{
  "word": "wine",
  "lang": "English",
  "lang_code": "en",
  "pos": "noun",
  "etymology_text": "From Middle English win, from Old English wīn, from Proto-Germanic *wīną, from Latin vīnum, from Proto-Italic *wīnom...",
  "etymology_templates": [
    {
      "name": "inh",
      "args": { "1": "en", "2": "enm", "3": "win" },
      "expansion": "Middle English win"
    },
    {
      "name": "inh",
      "args": { "1": "enm", "2": "ang", "3": "wīn" },
      "expansion": "Old English wīn"
    }
  ],
  "senses": [
    {
      "glosses": ["An alcoholic beverage made by fermenting grape juice"],
      "tags": ["countable", "uncountable"]
    }
  ],
  "sounds": [
    { "ipa": "/waɪn/", "tags": ["UK", "US"] }
  ],
  "forms": [
    { "form": "wines", "tags": ["plural"] }
  ]
}
```

### Key Fields for Our App

| Field | Use |
|-------|-----|
| `word`, `lang`, `pos` | Basic identification |
| `etymology_text` | Human-readable etymology narrative |
| `etymology_templates` | **Structured relationships** — this builds the graph |
| `senses[].glosses` | Definitions |
| `sounds[].ipa` | Pronunciation |

### Etymology Template Types (Graph Edges)

| Template | Meaning | Example |
|----------|---------|---------|
| `inh` | Inherited from | English "wine" ← Old English "wīn" |
| `bor` | Borrowed from | English "wine" ← Latin "vīnum" (if borrowed directly) |
| `der` | Derived from | General derivation |
| `cog` | Cognate with | Related word in another language |
| `m` | Mention | Reference to another word |

---

## Phase 0: Prototype (See Something Working)

**Goal**: Hardcoded etymology graph in vis.js
**Time**: 1-2 hours
**No database yet** — just prove the visualization works

### P0.1: Docker + vis.js Setup

```markdown
## Task: P0.1 - Basic Docker + vis.js

### What we're building
A simple web page that shows an etymology graph using vis.js.
No database, no API — just hardcoded data to prove the concept.

### Files to create

docker-compose.yml:
- nginx service on port 8080
- Mount frontend/public to nginx html

frontend/Dockerfile:
- Based on nginx:alpine

frontend/nginx.conf:
- Basic static file serving

frontend/public/index.html:
- Include vis.js from CDN (vis-network)
- Container div for the graph
- Basic styling

frontend/public/js/graph.js:
- Hardcoded data for "wine" etymology:
  wine (English) → wīn (Old English) → vīnum (Latin) → *wīnom (Proto-Italic)
- Create vis.js Network
- Nodes: word + language
- Edges: relationship type (inherited/borrowed)
- Hierarchical layout (ancestors above)

frontend/public/css/style.css:
- Full-height graph container
- Basic typography

### Acceptance criteria
- `docker compose up` works
- http://localhost:8080 shows graph
- Can see 4-5 nodes connected
- Can zoom/pan the graph
- Nodes show word + language
```

### P0.2: Add Search Box (Static)

```markdown
## Task: P0.2 - Static Search

### What we're building
A search box that switches between hardcoded word etymologies.

### Changes

frontend/public/index.html:
- Add search input at top
- Add word suggestions dropdown

frontend/public/js/search.js:
- Hardcoded list: wine, water, mother, father, three
- Filter as user types
- On select, emit event

frontend/public/js/app.js:
- Wire search selection to graph update
- Each word has hardcoded etymology data

frontend/public/js/graph.js:
- Add function: updateGraph(etymologyData)
- Clear and redraw with new data

### Hardcoded etymologies to include
1. wine: English → Old English → Latin → Proto-Italic → PIE
2. water: English → Old English → Proto-Germanic → PIE
3. mother: English → Old English → Proto-Germanic → PIE
4. father: English → Old English → Proto-Germanic → PIE
5. three: English → Old English → Proto-Germanic → PIE

### Acceptance criteria
- Type "wa" → shows "water" suggestion
- Click "water" → graph updates to water etymology
- Type "mo" → shows "mother"
- Graph clears and redraws smoothly
```

**✓ Prototype Checkpoint**: Can visualize etymology graphs, switch between words.

---

## Phase 1: MVP (Must-Haves)

**Goal**: Real Kaikki data in MongoDB, working search, automated setup
**Time**: 4-6 hours

### M1.1: MongoDB Container

```markdown
## Task: M1.1 - MongoDB Setup

### What we're building
Add MongoDB to Docker Compose for storing Kaikki data.

### Files to create/modify

docker-compose.yml:
- Add mongodb service
- Image: mongo:7
- Port: 27017
- Volume: ./data/mongodb:/data/db
- Health check

.env.example:
- MONGO_URI=mongodb://mongodb:27017/etymology

.gitignore:
- data/

### Acceptance criteria
- `docker compose up -d mongodb` starts MongoDB
- `docker compose exec mongodb mongosh` connects
- Data persists after restart (volume works)
```

### M1.2: Download Kaikki Data

```markdown
## Task: M1.2 - Download Script

### What we're building
Script to download the Kaikki English Wiktionary dump.

### Files to create

scripts/download-data.sh:
- Download from https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz
- Save to data/raw/
- Skip if file exists (unless --force flag)
- Show download progress
- Gunzip after download

Makefile:
- Add target: download

### Notes
- Full English dump is ~1GB compressed, ~5GB uncompressed
- For faster prototype, can use a subset (first 100K lines)

### Acceptance criteria
- `make download` fetches the file
- File appears in data/raw/kaikki-english.jsonl
- Running again skips download (file exists)
```

### M1.3: Load Data into MongoDB

```markdown
## Task: M1.3 - Load Kaikki into MongoDB

### What we're building
Script to load Kaikki JSONL into MongoDB.

### Files to create

backend/etl/load.py:
- Read kaikki-english.jsonl line by line
- Insert into MongoDB collection "words"
- Create indexes:
  - { word: 1, lang: 1 } - compound index for lookups
  - { word: "text" } - text index for search
  - { "etymology_templates.args.3": 1 } - for finding ancestors
- Show progress (every 10K records)
- Batch insert (1000 at a time) for performance

Makefile:
- Add target: load

### Performance notes
- ~1M English entries
- Should complete in 5-10 minutes on M1 Mac
- Use insert_many with ordered=False for speed

### Acceptance criteria
- `make load` populates MongoDB
- `db.words.countDocuments()` returns ~1M
- `db.words.findOne({word: "wine"})` returns data
- Indexes created (check with db.words.getIndexes())
```

### M1.4: Backend - FastAPI Setup

```markdown
## Task: M1.4 - FastAPI Basic Setup

### What we're building
FastAPI backend that connects to MongoDB.

### Files to create

backend/Dockerfile:
- Python 3.11-slim base
- Install requirements
- Run uvicorn

backend/requirements.txt:
- fastapi
- uvicorn[standard]
- motor (async MongoDB driver)
- pydantic-settings

backend/app/main.py:
- FastAPI app
- CORS middleware (allow frontend origin)
- Include routers
- Health check endpoint: GET /health

backend/app/config.py:
- Settings class with MONGO_URI from env

backend/app/database.py:
- Async MongoDB connection using motor
- Get database and collection helpers

docker-compose.yml:
- Add backend service
- Depends on mongodb
- Port 8000
- Environment variables

### Acceptance criteria
- `docker compose up backend` starts
- http://localhost:8000/health returns {"status": "ok"}
- http://localhost:8000/docs shows Swagger UI
```

### M1.5: Backend - Word Lookup API

```markdown
## Task: M1.5 - Word Lookup Endpoint

### What we're building
API endpoint to look up a word and get its data.

### Files to create

backend/app/routers/words.py:
- GET /api/words/{word}
- Query param: lang (default: "English")
- Returns full Kaikki entry
- 404 if not found

### Response format
{
  "word": "wine",
  "lang": "English",
  "pos": "noun",
  "definitions": ["An alcoholic beverage..."],
  "pronunciation": "/waɪn/",
  "etymology_text": "From Middle English...",
  "etymology_templates": [...]
}

### Acceptance criteria
- curl http://localhost:8000/api/words/wine returns data
- curl http://localhost:8000/api/words/xyznotaword returns 404
- ?lang=German returns German "wine" entry (if exists)
```

### M1.6: Backend - Etymology Chain API

```markdown
## Task: M1.6 - Etymology Chain Endpoint

### What we're building
API endpoint that extracts the etymology chain for visualization.

### Files to create

backend/app/routers/etymology.py:
- GET /api/etymology/{word}/chain
- Query param: lang (default: "English")
- Parse etymology_templates to build graph
- Return vis.js compatible format

### Algorithm
1. Get word document
2. Extract etymology_templates
3. For each template (inh, bor, der):
   - Source = current word
   - Target = template args (word in ancestor language)
   - Edge type = template name
4. Recursively fetch ancestors (if they exist in DB)
5. Limit depth to 10 to prevent infinite loops

### Response format (vis.js compatible)
{
  "nodes": [
    { "id": "wine:English", "label": "wine", "language": "English", "level": 0 },
    { "id": "wīn:Old English", "label": "wīn", "language": "Old English", "level": 1 },
    ...
  ],
  "edges": [
    { "from": "wine:English", "to": "wīn:Old English", "label": "inherited" },
    ...
  ]
}

### Acceptance criteria
- curl http://localhost:8000/api/etymology/wine/chain returns graph data
- Returns at least 3-4 ancestors for "wine"
- Unknown words return {"nodes": [...], "edges": []} (just the word itself)
```

### M1.7: Backend - Search API

```markdown
## Task: M1.7 - Search Endpoint

### What we're building
Text search endpoint for finding words.

### Files to create

backend/app/routers/search.py:
- GET /api/search
- Query param: q (search query)
- Query param: limit (default: 20)
- Uses MongoDB text search
- Returns list of matching words with basic info

### Response format
{
  "results": [
    { "word": "wine", "lang": "English", "pos": "noun" },
    { "word": "winery", "lang": "English", "pos": "noun" },
    ...
  ],
  "total": 42
}

### Acceptance criteria
- curl "http://localhost:8000/api/search?q=wine" returns results
- Results include wine, winery, winemaker, etc.
- Limit parameter works
- Empty query returns error
```

### M1.8: Frontend - Connect to API

```markdown
## Task: M1.8 - Connect Frontend to Real API

### What we're building
Replace hardcoded data with API calls.

### Files to modify

frontend/public/js/api.js:
- const API_BASE = 'http://localhost:8000/api'
- async function searchWords(query)
- async function getWord(word, lang)
- async function getEtymologyChain(word, lang)

frontend/public/js/search.js:
- Replace hardcoded list with API search
- Debounce input (300ms)
- Show loading state

frontend/public/js/app.js:
- On word select, call getEtymologyChain
- Pass result to graph.updateGraph()
- Handle errors gracefully

frontend/public/js/graph.js:
- updateGraph() now receives API format
- Map nodes/edges to vis.js format

frontend/public/index.html:
- Add loading spinner
- Add error message area

### Acceptance criteria
- Search box queries real API
- Selecting word shows real etymology
- Loading states visible
- Errors shown (e.g., network down)
```

### M1.9: Frontend - Graph Polish

```markdown
## Task: M1.9 - Graph Visualization Polish

### What we're building
Improve the graph to be more informative and usable.

### Files to modify

frontend/public/js/graph.js:
- Color nodes by language family:
  - English/Germanic: blue
  - Latin/Romance: red
  - Greek: green
  - Proto-Indo-European: gold
  - Other: gray
- Show edge labels (inherited, borrowed, derived)
- Hierarchical layout (ancestors at top)
- Click node → show detail panel

frontend/public/css/style.css:
- Side panel for word details
- Better typography
- Responsive layout

frontend/public/index.html:
- Add detail panel (hidden by default)
- Shows: word, language, definition, pronunciation

### Acceptance criteria
- Languages have distinct colors
- Edge types visible as labels
- Click node opens detail panel
- Graph readable with 10+ nodes
```

### M1.10: Automation

```markdown
## Task: M1.10 - One Command Setup

### What we're building
Makefile and scripts for complete automation.

### Files to create/modify

Makefile:
```makefile
.PHONY: setup run stop clean download load logs

setup: build download load
	@echo "✓ Setup complete! Run 'make run' to start."

build:
	docker compose build

download:
	./scripts/download-data.sh

load:
	docker compose up -d mongodb
	sleep 5  # Wait for MongoDB
	docker compose run --rm backend python -m etl.load

run:
	docker compose up -d
	@echo "✓ App running at http://localhost:8080"

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data/
```

README.md:
- Prerequisites (Docker, Make)
- Quick start: `make setup && make run`
- Available commands
- Troubleshooting

### Acceptance criteria
- Fresh clone + `make setup && make run` → working app
- Works on Mac (Apple Silicon + Intel)
- README is clear and complete
```

**✓ MVP Checkpoint**: Full Kaikki data, real search, graph visualization, one-command setup.

---

## Phase 2: Nice-to-Haves

Pick and choose based on interest:

### N2.1: Cognate View
Show related words across languages (same PIE root).

### N2.2: Language Family Filter
Dropdown to show only Germanic, Romance, etc.

### N2.3: Dark Mode
Toggle for dark theme, persist in localStorage.

### N2.4: Shareable URLs
URL updates with selected word (e.g., `/#/wine`), browser back works.

### N2.5: Static Export
`make export WORD=wine` creates standalone HTML for GitHub Pages.

### N2.6: Bulk Export
Export top 1000 words as static site for GitHub Pages.

### N2.7: Word Details Panel
Richer detail view: all definitions, examples, related words.

### N2.8: Performance
Lazy-load distant ancestors, handle large graphs (100+ nodes).

---

## Claude Code Session Plan

### Session 1: Prototype (P0) — ~1 hour
```
P0.1 → P0.2 → Test
Checkpoint: See hardcoded graphs, can switch between words
```

### Session 2: Database (M1.1-M1.3) — ~1.5 hours
```
M1.1 → M1.2 → M1.3 → Test
Checkpoint: Kaikki data loaded in MongoDB
```

### Session 3: Backend (M1.4-M1.7) — ~1.5 hours
```
M1.4 → M1.5 → M1.6 → M1.7 → Test
Checkpoint: All API endpoints working
```

### Session 4: Integration (M1.8-M1.10) — ~1.5 hours
```
M1.8 → M1.9 → M1.10 → Test
Checkpoint: MVP complete!
```

### Session 5+: Nice-to-Haves
Pick 2-3 based on what you want most.

---

## Task Card Template for Claude Code

Each task should be given in this format:

```markdown
## Task: [ID] - [Name]

### Context
[What's already built, what this connects to]

### Requirements
[What needs to be created/changed]

### Files to create/modify
[Explicit list]

### Technical details
[Specific implementation notes]

### Acceptance criteria
[How to verify it works]
```

---

## Environment Variables

```bash
# .env.example
MONGO_URI=mongodb://mongodb:27017/etymology
```

---

## Estimated Time

| Phase | Tasks | Time |
|-------|-------|------|
| P0: Prototype | 2 | 1-2 hours |
| M1: MVP | 10 | 4-6 hours |
| N2: Nice-to-Haves | 8 | 3-5 hours |
| **Total** | **20** | **8-13 hours** |

---

## Future Migration Path

If you outgrow MongoDB:

| Trigger | Migration |
|---------|-----------|
| Need complex joins | → PostgreSQL with JSONB |
| Heavy graph traversal | → Neo4j for relationships |
| Full-text search limitations | → Add Elasticsearch |
| Need embeddings/semantic search | → Add pgvector or Pinecone |

The data remains portable — JSON in, JSON out.

---

*Document updated: January 30, 2026*
*Stack: MongoDB + FastAPI + vis.js + Docker Compose*
