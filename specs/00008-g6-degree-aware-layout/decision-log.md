# Decision Log — SPC-00008: G6 Degree-Aware Force Layout

## Starting Question

The G6 renderer uses uniform force parameters, producing dense clusters where vis.js has readable, well-spaced layouts. How should we match the layout quality?

## Alternatives Considered

### Option A: Copy vis.js parameter values directly
- Pro: Exact same layout
- Con: Different physics engines (d3-force vs forceAtlas2Based) — same parameters produce different results

### Option B: Port the vis.js formulas, tune values for d3-force
- Pro: Same mathematical relationships (logarithmic scaling by degree, exponential decay by level)
- Con: Requires visual tuning iteration

### Option C: Use a different G6 layout algorithm (dagre, circular)
- Pro: Different strengths for different graph types
- Con: Not comparable to vis.js's force-directed feel

## Decision & Rationale

**Option B**. The vis.js formulas (`graph.js:534-578`) encode good design decisions about degree-aware spacing. We port the relationships (log-degree distance, exponential-level charge decay) but expect to tune absolute values since d3-force and forceAtlas2Based interpret parameters differently. The formulas are:
- Edge distance: `110 + 50 * log2(1 + combined_degree)` — same as vis.js
- Charge: `-2000` (root), `-500 / 2^|level|` (others) — adapted from vis.js mass formula
- Edge opacity: `max(0.2, 1/log2(2 + maxDeg))` — same as vis.js

Root pinning via d3-force `fx`/`fy` is the standard approach; vis.js uses `fixed: {x: true, y: true}`.

## Participants

- **Human** — requested layout parity between renderers
- **Claude (Development Agent)** — analyzed both physics engines, designed the parameter mapping
