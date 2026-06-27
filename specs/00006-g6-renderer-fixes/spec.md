# SPC-00006: G6 Renderer Fixes

| Field | Value |
|---|---|
| **Status** | deprecated |
| **Created** | 2026-02-11 |
| **Deprecated** | 2026-06-27 (AUDIT-2026-06: G6 renderer abandoned) |
| **Modifies** | SPC-00005 (fixes the experimental G6 renderer) |
| **Modified-by** | — |

> **DEPRECATED.** This folder holds three bug reports against the experimental G6 adapter
> (`g6-adapter.js`), which was never merged to `main` and does not exist in the codebase. The bugs
> are moot. See [SPC-00005](../00005-g6-experimental-renderer/spec.md) and the
> [2026-06 audit](../../docs/AUDIT-2026-06.md#a2--dead-weight--rot).

## Contents (historical)

Three open bug reports from the G6 exploration:

- `bug-001-node-click-during-animation.md`
- `bug-002-canvas-click-deselect.md`
- `bug-003-wrong-node-on-reselect.md`

All three describe interaction defects in the abandoned G6 renderer. They are retained for history
only; none apply to the shipped vis.js renderer.
