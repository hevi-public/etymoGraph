# Decision Log — SPC-00007: Shared Graph Utility Extraction

## Starting Question

How should G6 renderers access the BFS hop-distance computation currently embedded in vis.js-specific code (`graph.js`)?

## Alternatives Considered

### Option A: Duplicate the BFS logic in each G6 adapter
- Pro: No changes to existing files
- Con: Three copies of the same algorithm (graph.js, g6-adapter.js, g6-concept-adapter.js)

### Option B: Extract to graph-common.js with configurable edge field names
- Pro: Single source of truth, already loaded before all renderers
- Con: Requires converting vis.js DataSet to array at call site (trivial)

### Option C: Create a new shared module
- Pro: Clean separation
- Con: Another script tag, another file to maintain; graph-common.js already serves this purpose

## Decision & Rationale

**Option B**. `graph-common.js` already contains shared constants (`OPACITY_BY_HOP`, `opacityForHops`, `colorWithOpacity`) used by the brightness system. Adding the BFS function there keeps related code together. The `fromKey`/`toKey` parameters handle the vis.js `{from,to}` vs G6 `{source,target}` difference without forcing either format.

## Participants

- **Human** — requested G6 feature parity
- **Claude (Development Agent)** — identified the extraction opportunity, designed the interface
