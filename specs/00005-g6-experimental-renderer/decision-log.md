# Decision Log: SPC-00005 G6 Experimental Renderer (deprecated)

## Starting Question

Could [AntV G6](https://g6.antv.antgroup.com/) replace or complement vis.js as the graph renderer?
G6 offers a richer node/edge styling model, a first-class state system (useful for highlight/dim),
and more granular layout control than vis.js's physics presets.

## Alternatives Considered

### Option A: Stay on vis.js (chosen, by default)

- **Pros:** Already shipped and polished — two pluggable layouts, deterministic seed, degree-aware
  physics, radial seeding + barycentric refinement, large-graph LOD/clustering (SPC-00004). No build
  step. One renderer to maintain.
- **Cons:** vis.js styling and state handling are coarser than G6's; some highlight effects are
  harder to express.

### Option B: Add G6 as a second, toggleable renderer

- **Pros:** Best-of-both per view; an escape hatch if vis.js hit a wall.
- **Cons:** **Doubles the maintenance surface** — every graph feature (highlight/dim, layout,
  trackpad/touch, LOD, clustering) must be implemented twice. The follow-on specs SPC-00006–00010
  are evidence of this cost: a renderer barely stood up already needed five specs and three bug
  reports to reach parity on basics.

### Option C: Migrate fully from vis.js to G6

- **Pros:** Single modern renderer.
- **Cons:** Throws away working, polished vis.js behavior for a speculative gain; high risk.

## Decision & Rationale

**Option A.** The G6 branch was abandoned and never merged. vis.js already met the product's needs,
and the marginal benefit of G6 did not justify carrying a second renderer through every future graph
feature. The exploration's one durable, renderer-agnostic idea — extracting shared graph utilities
(SPC-00007) — is retained as structural-debt guidance for the existing vis.js code.

This spec was created retroactively (2026-06-27) during the feature audit to:

1. Give SPC-00006–00010's `Modifies: SPC-00005` references a real target (CLAUDE.md mandates
   bidirectional spec traceability; the dangling reference broke it).
2. Repair `CLAUDE.md`, which pointed at this nonexistent folder as its "canonical decision-log
   example."
3. Record *why* the G6 line was dropped, so a future contributor doesn't rediscover it cold.

## Participants

- **Human:** Initiated the G6 exploration (Feb 2026); decided not to merge.
- **Claude (DA):** Built the G6 adapter on a feature branch; back-filled this deprecation record
  during the 2026-06 audit.
