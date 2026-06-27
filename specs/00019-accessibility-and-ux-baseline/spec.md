# SPC-00019: Accessibility & UX Baseline

| Field | Value |
|---|---|
| **Status** | draft |
| **Created** | 2026-06-27 |
| **Modifies** | SPC-00003 (adds "copy share link" + history trail to the URL-routing UX) |
| **Modified-by** | — |

## Problem

The app has no accessibility baseline and several missing navigation affordances
([AUDIT-2026-06 §A5](../../docs/AUDIT-2026-06.md#a5--ux--accessibility--polish)):

- Search autocomplete is **mouse-only** (no arrow/Escape keys); **zero ARIA / `aria-live`**; focus
  rings stripped from several controls.
- Language families are encoded by **hue alone** (colorblind-hostile; some near-duplicate colors).
- **No `@media` queries** — the surrounding chrome doesn't reflow on mobile.
- Etymology fetch failures are **silent**; no loading or empty states.
- Missing cheap navigation wins: no in-app history/breadcrumb, the legend is display-only, no
  filter-by-family, no "copy share link" despite shareable links being a headline feature.

## Goals

- Make the core flows usable by keyboard and screen reader.
- Make encodings perceivable without color.
- Give clear feedback for loading/error/empty states.
- Add the low-cost navigation affordances users expect.
- Reflow acceptably on a phone.

## Proposed solution

### Accessibility
- **Keyboard autocomplete:** Up/Down to move through suggestions, Enter to select, Escape to close;
  manage focus and `aria-activedescendant`.
- **ARIA:** combobox/listbox roles on search; `aria-live="polite"` on `#concept-status` and on a new
  graph-status region; labelled buttons; `role`/labels on the detail panel open/close.
- **Focus visibility:** restore visible focus rings on all interactive controls (remove the blanket
  `outline: none`).
- **Color independence:** add a redundant cue to language family beyond hue — a short family label or
  pattern/shape on nodes and the legend — and ship a colorblind-safe palette option.

### Feedback states
- Loading indicators for etymology/concept fetches; a user-visible error banner on failure
  (replace the silent `console.error` in `app.js`); an empty/"no results" state in search.

### Navigation affordances
- **History/breadcrumb trail** of in-app `selectWord` jumps (distinct from browser back/forward).
- **Click-the-legend to isolate/dim** a family (and an era band in era-layered).
- **Filter by language/family** before or after searching.
- **"Copy share link"** button (builds on SPC-00003's URL state).

### Responsive
- Add `@media` breakpoints so the header controls, detail panel, and legend reflow on narrow
  viewports (the canvas already has touch handlers).

## Out of scope
- The `graph.js` refactor / shared-utilities extraction (tracked as structural debt; see the
  deprecated SPC-00007 note). This spec is behavior/UX, not internal restructuring — though the
  duplicated trackpad/touch code is a natural thing to consolidate while touching these handlers.

## Verification
- Full search → select → explore flow is operable by keyboard alone; a screen reader announces
  suggestions and status changes.
- Family distinctions are legible in a grayscale/colorblind simulation.
- Forced fetch failures show a visible error; slow loads show progress.
- Layout is usable at ~375px width.
