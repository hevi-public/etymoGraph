# Decision Log — SPC-00006: G6 Renderer Fixes

## Starting Question

After implementing the G6 v5 experimental renderer (SPC-00005), three usability issues were identified during manual testing: no physics animation, crowded nodes, and broken trackpad interaction on macOS. How should these be fixed?

## Alternatives Considered

### Fix 1: Physics Animation

- **Option A: `animate: true` on d3-force layout** — G6's built-in support for rendering intermediate layout ticks. Minimal code change.
- **Option B: Custom tick callback with manual position updates** — More control but significantly more complex and fragile.
- **Decision:** Option A. The `animate` flag is purpose-built for this and requires a single line.

### Fix 2: Force Spacing

- **Option A: Increase force parameters** — Stronger charge repulsion (-500 vs -300), larger link distance (200 vs 150), bigger collision radius (50 vs 30).
- **Option B: Switch to a different layout algorithm** — e.g., `dagre` for hierarchical layouts.
- **Decision:** Option A. The d3-force layout is the right choice for etymology graphs (similar to vis.js forceAtlas2Based). Just needed parameter tuning. Values were estimated then verified visually with "wine" and "water" graphs.

### Fix 3: Trackpad Interaction

- **Option A: Replace `zoom-canvas` with `scroll-canvas` + custom pinch handler** — `scroll-canvas` handles two-finger pan natively. A small custom `wheel` listener with `ctrlKey` check handles pinch-to-zoom. Mirrors the proven pattern in `graph.js`.
- **Option B: Configure `zoom-canvas` to ignore non-pinch events** — G6's zoom-canvas behavior doesn't expose this level of control in v5.
- **Option C: Implement a full custom behavior plugin** — Overkill for this use case.
- **Decision:** Option A. Clean separation of concerns: G6 handles pan, custom code handles pinch. Pattern already proven in vis.js renderer.

## Decision & Rationale

All three fixes were bundled into a single spec because they're all scoped to one file (`g6-adapter.js`) and address the same root issue: "G6 renderer UX doesn't match vis.js quality." Each fix is minimal and targeted, avoiding over-engineering.

The `drag-element-force` behavior was chosen over `drag-element` to complement the animated physics — when a user drags a node, the force simulation should respond in real-time, pushing nearby nodes away. This creates a cohesive physics-based interaction model.

## Participants

- **Human** — identified the three issues during manual testing
- **Claude (Development Agent)** — investigated G6 v5 API, proposed solutions, implemented fixes
