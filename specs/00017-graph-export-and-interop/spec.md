# SPC-00017: Graph Export & Interoperability

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | — |
| **Modified-by** | — |

## Problem

There is no way to get anything *out* of the tool — no image to share, no data file to analyze
elsewhere. This blocks two audiences at once: hobbyists who want to share a word's story as a
picture, and linguists who want to take the graph into Gephi, a phylogenetics package, or a
reproducible dataset. The original plan's "static export" / "bulk export" (N2.5/N2.6) remain
unstarted.

## Goals

- **Image export** of the current graph (PNG, and SVG where feasible) for sharing/citation.
- **Structured data export** of the current graph (and optionally a word's full subtree) in
  standard, tool-friendly formats.
- A discoverable **Export** affordance in the UI.

## Proposed solution

### Image export (client-side)
- Export the vis.js canvas to **PNG** via `canvas.toBlob`. Offer an **SVG** path if a vector export
  is practical (vis.js is canvas-based; an SVG re-render of the current nodes/edges may be needed).
- Include a title/caption (word + language) and a small attribution footer (Wiktionary/Kaikki).

### Structured export (backend endpoint)
A `GET /api/etymology/{word}/export?format=…&lang=…&types=…` returning the same graph the tree
endpoint builds, serialized as:
- **GraphML** and **GEXF** — for Gephi / general network tools.
- **Newick** / **Nexus** — for the *tree-shaped ancestry* projection (phylogenetics tools); clearly
  documented as the inheritance spanning tree, since the full graph is not a tree.
- **CLDF** (Cross-Linguistic Data Formats) — a `cognates`/`forms` table export aligned with the
  comparative-linguistics ecosystem.
- **JSON** — the raw nodes/edges (already the API's internal shape).

### UI
- An "Export ▾" menu near the zoom controls: *PNG*, *SVG*, *GraphML*, *Newick*, *CLDF*, *JSON*.
- Each download is named `{word}-{lang}.{ext}`.

## Out of scope
- A full static-site generator for GitHub Pages (N2.5) and bulk top-1000 export (N2.6) — these can
  build on the per-graph JSON/image export here in a later spec.

## Verification
- PNG/SVG downloads render the visible graph faithfully with caption + attribution.
- GraphML/GEXF open in Gephi; Newick opens in a tree viewer (FigTree); CLDF validates against the
  CLDF spec; JSON round-trips to the API shape.
