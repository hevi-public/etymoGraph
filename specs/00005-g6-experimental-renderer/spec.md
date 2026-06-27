# SPC-00005: G6 Experimental Renderer

| Field | Value |
|---|---|
| **Status** | deprecated |
| **Created** | 2026-02-11 |
| **Deprecated** | 2026-06-27 (AUDIT-2026-06: abandoned, never merged) |
| **Modifies** | — |
| **Modified-by** | SPC-00006, SPC-00007, SPC-00008, SPC-00009, SPC-00010 (G6 follow-on specs, all deprecated alongside this one) |

> **DEPRECATED.** This spec is back-filled to close out an abandoned line of work and to repair
> dangling cross-references. The G6 renderer was explored on the unmerged branch
> `spc-00005-g6-renderer` and never landed on `main`. **No G6 / AntV code exists in the codebase.**
> The shipped product uses vis.js exclusively. See the [2026-06 audit](../../docs/AUDIT-2026-06.md#a2--dead-weight--rot).

## What this was

An experiment to add [AntV G6](https://g6.antv.antgroup.com/) as an alternative graph renderer
alongside vis.js, motivated by G6's richer styling, state system, and layout controls. The
exploration produced an adapter (`g6-adapter.js`) and a `graph-common.js` shared-utilities module on
a feature branch, plus a cluster of follow-on specs:

- **SPC-00006** — G6 renderer fixes (three open bug reports: click-during-animation, canvas-click
  deselect, wrong-node-on-reselect).
- **SPC-00007** — extract `computeHopDistances` into `graph-common.js` for renderer reuse.
- **SPC-00008** — degree-aware force layout for G6.
- **SPC-00009** — hop-distance highlight/dim for the G6 etymology graph.
- **SPC-00010** — connected-node highlight for the G6 concept map.

## Why it was abandoned

The vis.js renderer already satisfied the product's needs (two pluggable layouts, deterministic
seeding, degree-aware physics, large-graph performance work in SPC-00004). Maintaining a **second
renderer** doubled the surface area for every graph feature — highlight/dim, layout, trackpad/touch,
LOD — for limited user-facing benefit. The branch was never merged; the follow-on specs never left
`draft`/`Open`.

## Resolution

- This spec is recorded as `deprecated` so the `Modifies: SPC-00005` references in SPC-00006–00010
  resolve to a real document, restoring bidirectional traceability.
- SPC-00006–00010 are marked `deprecated`.
- `CLAUDE.md`'s "canonical decision-log example" pointer is repointed away from this folder to a
  spec that was actually implemented.

## If revived

The shared-utilities idea from **SPC-00007** (`graph-common.js`) is independently worth doing — the
trackpad/touch/LOD/hop-distance logic is currently **duplicated** between `graph.js` and
`concept-map.js` (~120 lines), regardless of renderer. Extracting it is tracked as structural debt in
the audit and would benefit the existing vis.js code today. Reviving G6 itself should start from a
fresh spec that justifies a second renderer against current product priorities.
