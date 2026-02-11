# Decision Log — SPC-00009: G6 Etymology Graph Highlight/Dim

## Starting Question

How should G6 implement the hop-based highlight/dim behavior that vis.js provides via manual rgba color updates?

## Alternatives Considered

### Option A: G6 state system with 3 named states
- Pro: Idiomatic G6 approach, `opacity` applies to entire group (shape+label), batch `setElementState` for performance, automatic reset by clearing states
- Con: Discrete opacity levels only (not arbitrary values per node)

### Option B: Direct style updates via `graph.updateNodeData()`
- Pro: Arbitrary opacity per node (could exactly match vis.js's continuous gradient)
- Con: Must manually track and restore all base styles on reset, more complex code

### Option C: G6 plugins / behaviors
- Pro: Encapsulated as reusable behavior
- Con: G6 v5 behavior API is complex, overkill for this use case

## Decision & Rationale

**Option A**. The 4 discrete opacity levels from vis.js (`OPACITY_BY_HOP = [1.0, 0.9, 0.5, 0.1]`) map directly to 3 named states + default. G6's state system handles reset automatically (clear states = return to default). The batch `setElementState({...})` API applies all changes in one render pass. This is simpler, more performant, and more maintainable than manual style updates.

The state `opacity` multiplies with any existing rgba alpha in stroke colors (degree-based edge opacity from SPC-00008). This is the correct behavior — a dim edge between high-degree nodes should be even dimmer than a dim edge between low-degree nodes.

## Participants

- **Human** — requested click-to-highlight and dim features
- **Claude (Development Agent)** — evaluated G6 v5 APIs, chose state system approach
