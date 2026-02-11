# Decision Log — SPC-00010: G6 Concept Map Highlight

## Starting Question

Should the G6 concept map use the same hop-based dimming as the etymology graph (SPC-00009), or the simpler binary highlight that vis.js uses?

## Alternatives Considered

### Option A: Binary highlight (connected vs. not) — match vis.js
- Pro: Matches existing behavior users expect, simpler implementation, concept maps show similarity not ancestry so hop distance is less meaningful
- Con: Less granular than hop-based

### Option B: Hop-based dimming — same as etymology graph
- Pro: Consistent behavior across both views
- Con: Concept maps are typically denser (more edges per node), so hop-based dimming would leave most nodes at 1-2 hops, reducing its usefulness. Also doesn't match vis.js behavior.

## Decision & Rationale

**Option A**. The concept map's structure is fundamentally different from the etymology graph: it shows phonetic similarity (many lateral connections) rather than ancestry (tree-like). In a dense similarity graph, most nodes are 1-2 hops away, making hop-based dimming ineffective. Binary highlighting clearly answers "what is this node connected to?" — the primary user question when clicking a concept map node.

Additionally, matching vis.js's existing behavior avoids confusing users who switch between renderers.

## Participants

- **Human** — requested feature parity between renderers
- **Claude (Development Agent)** — analyzed concept map graph structure, chose binary approach
