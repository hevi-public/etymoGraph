# SPC-00005: Decision Log — WebGL Graph Library Selection

> Architecture Decision Record documenting the research journey from initial question
> to G6 v5 selection. Written collaboratively by a human developer and Claude (Opus 4.6)
> over a single conversation session.

---

## 1. Starting Question

**Human asked:** "Do you think it would be beneficial for performance (and maintenance) to migrate the vis.js use cases over to WebAssembly or WebGL? What are the pros/cons? How feasible is the work?"

This was not a request to migrate — it was a genuine exploration of trade-offs.

## 2. Initial Assessment: Against Migration

**Agent used:** Explore (Sonnet) — analyzed graph.js (~1500 lines), concept-map.js (~450 lines), and SPC-00004 performance spec.

**Findings from codebase analysis:**
- Typical graphs: 200-1000 nodes, tested smooth up to ~3000
- SPC-00004 already implemented comprehensive optimizations:
  - R1: Straight edges for 200+ nodes (eliminated Bezier overhead)
  - R2: LOD — labels hidden below 0.4 scale
  - R3: Clustering by language family below 0.25 scale
  - R4: Disabled `improvedLayout` for 200+ nodes
  - R5: Physics frozen after stabilization
  - R7: barnesHut solver fallback for 1000+ nodes
- 10 distinct vis.js features in use (physics, reactive data, styling, interactions, layouts, LOD, clustering, canvas hooks, hit detection, stabilization)
- Rewrite estimate: 2000-3000 lines of custom physics + rendering code
- Timeline estimate: 3-6 months full-time

**Initial conclusion:** No current performance problem exists. A WebGL migration would be premature optimization — far more effort for the same result at current graph sizes. The diagnostic-first approach in SPC-00004 was exactly right.

**Pros identified:**
| Benefit | When it matters |
|---------|----------------|
| 10-100x rendering throughput | 10,000+ nodes |
| GPU-accelerated edge drawing | Thousands of simultaneous edges |
| WASM physics (C/C++ compiled) | 5,000+ node force simulations |
| Future-proof for massive graphs | Entire language family trees |

**Cons identified:**
| Cost | Impact |
|------|--------|
| 3-6 month rewrite | graph.js ~1,500 lines; need ~3,000+ for renderer + physics + interactions |
| Reimplement everything vis.js gives you | Clustering, hit detection, viewport animation, drag handling, solvers |
| Long-term maintenance burden | Own the rendering engine forever |
| No existing problem to solve | SPC-00004 already confirmed 60fps at realistic sizes |

## 3. Context Shift: Huge Graphs Are Coming

**Human revealed:** "What you've said in 'Pros of WebGL/WASM', they are coming. We will need to display huuuggeeeee graphs in the near future. Hence the question. Preparing for the future."

This changed the calculus from "premature optimization" to "necessary preparation." The question shifted from "should we?" to "which library?"

## 4. Library Research — Broad Scan

**Agents used:** 2x Explore (Sonnet) running in parallel
- Agent 1: Sigma.js + Graphology deep dive
- Agent 2: Deck.gl, Ogma, Cytoscape.js, G6, Cosmograph, and other options

**8 candidates evaluated:**

### Immediately Eliminated (4)

| Library | Reason for Elimination |
|---------|----------------------|
| **Deck.gl** | Geospatial/map framework, not graph visualization. `graph.gl` showcase is unmaintained. Wrong tool. |
| **Ogma** | Commercial license, no public pricing, must contact sales. Vendor lock-in risk. |
| **Reagraph** | React-only dependency. Project uses vanilla JS with no build step. Non-starter. |
| **NetV.js** | Academic project (Zhejiang University), only 50K node capacity, limited styling, slow maintenance. Not production-ready. |

### Shortlisted for Deep Analysis (4)

| Library | Initial Score | Key Strength | Key Concern |
|---------|--------------|--------------|-------------|
| **Sigma.js + Graphology** | 7/10 features | WebGL-native, lightweight | No clustering API, 2-person team |
| **Cytoscape.js** | 8/10 features | Most mature (11 years) | WebGL renderer experimental |
| **G6 v5 (AntV)** | 8-9/10 features | Best feature parity | Chinese-centric community |
| **Cosmograph (cosmos.gl)** | 5/10 features | 1M+ node GPU performance | Only 7 contributors |

## 5. Feature Parity Analysis

Mapped all 10 current vis.js features against each candidate:

| Requirement | Sigma.js | Cytoscape.js | G6 v5 | Cosmograph |
|---|---|---|---|---|
| 1. Force physics | ForceAtlas2 via graphology | Multiple algorithms | ForceAtlas2 + Rust layouts | GPU-accelerated |
| 2. Reactive data | Full | Full | Full | Full |
| 3. Node styling (box, dashed, opacity) | **Custom WebGL shader needed** | Full (CSS-like) | Full | Limited |
| 4. Edge styling (6 types, arrows, dashed) | Full | **WebGL: no dashed edges** | Full | Basic |
| 5. Interaction (click, drag, zoom, animate) | Full | Full | Full | Zoom/pan/drag |
| 6. Clustering (collapse/expand) | **Must build yourself** | Limited | Built-in | None |
| 7. Custom canvas hooks (era bands) | Layer API (different) | Layer system | Custom layer | Unclear |
| 8. LOD (label hiding, zoom clustering) | Via reducers (manual) | Manual control | Built-in | Unclear |
| 9. Hit detection | Automatic | Automatic | Automatic | Automatic |
| 10. Stabilization callbacks | **No equivalent** | Layout events | Layout events | Unclear |

**Performance ceilings:**

| Library | Rendering | Smooth ceiling | Max tested |
|---|---|---|---|
| vis.js (current) | Canvas 2D | ~3K nodes | ~10K (laggy) |
| Sigma.js | WebGL | ~10K nodes | 100K edges |
| Cytoscape.js | Canvas + WebGL preview | ~10K (WebGL) | Unknown |
| G6 v5 | Canvas/SVG/WebGL | ~10K nodes | Rust layouts for larger |
| Cosmograph | WebGL (full GPU) | **1M+ nodes** | Millions |

## 6. Project Health Deep Dive

**Agent used:** Explore (Sonnet) — researched GitHub metrics, npm stats, contributor activity, governance, and contribution friendliness for all 4 finalists.

### Cosmograph / cosmos.gl
- **Stars:** 1,100 | **Contributors:** 7 | **Last release:** v2.6.1 (Nov 2025)
- **Core maintainers:** 2 (Nikita Rokotyan, Olya Stukova)
- Joined OpenJS Foundation May 2025 as **incubating** project
- CONTRIBUTING.md exists, but only 7 total contributors — very small team
- Commercial product (Cosmograph) built on open-source core (cosmos.gl)
- **Bus factor: Very High** — essentially a 2-person effort

### G6 v5 by AntV
- **Stars:** 12,000 | **Contributors:** 211 | **Last release:** v5.0.49 (June 2025)
- **npm downloads:** ~161K/week | **Test coverage:** 90.44%
- Primary development by Ant Group (Alibaba affiliate)
- **Actively seeking external contributors** — "Looking for Contributors!" issue, summer of code program
- Recent external PRs merged from non-Alibaba developers
- English docs available and decent; primary community is Chinese
- **Bus factor: Low** — institutional backing + large contributor base

### Cytoscape.js
- **Stars:** 10,800 | **Contributors:** 246+ | **Age:** 11 years (since 2015)
- **npm downloads:** 1.5M-3.4M/week (highest by far)
- **Release cadence:** Features monthly, patches weekly
- WebGL renderer since v3.31 (Jan 2025) — **still experimental** after 1+ year
- Explicit invitation for contributors: *"Would you like to become a Cytoscape.js contributor?"*
- **Bus factor: Very Low** — largest community, longest track record

### Sigma.js + Graphology
- **Stars:** 11,900 (sigma) + 1,600 (graphology) | **Core maintainers:** 2
- **Last release:** sigma v3.0.2 (May 2025), graphology v0.26.0 (Feb 2025)
- v4 status: *"barely even a project yet"* — hoped for 2025, no guarantees
- Maintainers focused on **Gephi Lite** (their primary project)
- No CONTRIBUTING.md found, only 3 open PRs
- **Bus factor: High** — 2 core maintainers with split attention

### Contribution Friendliness Ranking
1. **Cytoscape.js** — Explicit invitation, monthly/weekly releases, 246+ contributors
2. **G6** — Actively seeking contributors, summer of code, 211 contributors
3. **Sigma.js** — Small team, unclear process
4. **Cosmograph** — Very small team, new governance

## 7. Human Question: Freshness and Contribution

Human asked about project freshness, whether we could contribute PRs, and which library Claude would prefer to work with.

**Claude's preference: G6 v5**, reasoning:
- Best feature parity today (8-9/10 requirements met out of the box)
- Migration would be 1:1 feature replacement rather than building custom clustering or WebGL shaders
- 211-contributor ecosystem means bugs get fixed without us carrying the load
- Chinese-language community is navigable (Claude reads Chinese)

**Cytoscape.js as fallback**, reasoning:
- Safest long-term bet: 11 years old, 1.5M weekly downloads, lowest abandonment risk
- But WebGL story is experimental — Canvas performance same as vis.js
- Migration only pays off when their WebGL renderer matures

## 8. Final Decision

| Role | Selection |
|------|-----------|
| **Primary** | G6 v5 by AntV |
| **Fallback** | Cytoscape.js |
| **Architecture** | Renderer abstraction layer — both coexist, user switches via UI |
| **Strategy** | Add alongside vis.js as experimental, do not replace |

### Why G6 wins
1. **Feature parity:** Built-in clustering, LOD, ForceAtlas2, WebGL — less custom code to write and maintain
2. **Performance headroom:** Rust-accelerated layouts, WebGL rendering, designed for large graphs
3. **Active community:** 211 contributors, institutional backing, actively welcoming external PRs
4. **Practical migration:** 3-4 week estimate for Phase 1 (basic rendering), vs. 4-6 weeks for Sigma.js (must build clustering + custom shaders)

### Why not the others
- **Sigma.js:** No clustering API (must build from scratch), no stabilization callbacks, 2-person team with split attention, v4 stalled
- **Cytoscape.js:** WebGL renderer experimental for 1+ year, Canvas performance = vis.js (no gain), waiting for maturity
- **Cosmograph:** 7 contributors, limited styling/interaction, would need to build most features ourselves on top of a rendering engine

## Participants

| Who | Role | Contributions |
|-----|------|---------------|
| **Human developer** | Decision-maker, domain expert | Initiated research question, provided future scale requirements, directed investigation priorities, chose final architecture (experimental alongside vis.js) |
| **Claude (Opus 4.6)** | Research lead, technical analyst | Conducted codebase analysis, synthesized multi-library comparisons, provided recommendations with trade-off analysis, designed spec |
| **Explore agents (Sonnet)** | Parallel researchers | 4 agents total: (1) vis.js usage analysis, (2) Sigma.js deep dive, (3) Deck.gl/Ogma/alternatives scan, (4) project health metrics for all 4 finalists |
| **Plan agent (Sonnet)** | Architecture designer | Detailed G6 API mapping, phased implementation plan, code structure design, risk analysis |

## Timeline

This entire research-to-decision process occurred in a single conversation session. The progression:

1. Open-ended question about WebGL/WASM
2. Initial "don't migrate" recommendation (based on current needs)
3. User context shift → "huge graphs are coming"
4. Broad 8-library scan with parallel research agents
5. Narrowing to 4 finalists with feature parity matrix
6. Project health deep dive (GitHub metrics, npm stats, governance)
7. Final selection: G6 primary, Cytoscape.js fallback
8. Spec design with phased implementation plan

---

*This decision log accompanies SPC-00005 (spec.md) and is intended as a reference for the team on how the library selection was made.*
