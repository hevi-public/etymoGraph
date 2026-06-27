# Decision Log: SPC-00019 Accessibility & UX Baseline

## Starting Question

The audit found no accessibility baseline (no keyboard nav, no ARIA, color-only encoding, no mobile
reflow, silent errors) plus several missing low-cost navigation affordances. How much should one
spec take on, and what's the right grouping?

## Alternatives Considered

### Option A: One narrow a11y spec, defer the navigation wins
- **Pros:** Tightly scoped.
- **Cons:** The cheap nav wins (breadcrumb, legend isolation, copy-link, family filter) touch the
  same files (`app.js`, `index.html`, `style.css`, the legend in `graph.js`) and the same review
  pass; splitting them creates churn for little benefit.

### Option B: Fold a11y + feedback states + cheap nav wins into one "UX baseline" (chosen)
- **Pros:** One coherent pass over the interaction layer; ships a noticeably more polished tool;
  shared review/testing.
- **Cons:** Larger spec; must be careful not to absorb the `graph.js` refactor.

### Option C: Bundle the structural `graph.js` refactor too
- **Pros:** "Fix it all at once."
- **Cons:** Conflates risky internal restructuring with user-facing UX; harder to review and verify.
  Kept out of scope (left as structural debt, cf. deprecated SPC-00007).

## Decision & Rationale

**Option B.** The accessibility fixes, feedback states, and cheap navigation wins are one coherent
interaction-layer pass and share files and tests; bundling them produces a single, reviewable
quality jump. The `graph.js` god-file refactor is explicitly excluded to keep behavior changes
separate from internal restructuring — though consolidating the duplicated trackpad/touch handlers
is fair game when editing them.

### Sub-decision: redundant color encoding over palette-only
Rather than only swapping in a colorblind-safe palette, add a **redundant** non-color cue (family
label/pattern). 21 families exceed the count any palette can keep reliably distinguishable, so color
alone can't be the sole channel.

## Participants

- **Human:** Asked for a tool usable by a broad audience (linguists and hobbyists alike).
- **Claude (DA):** Grouped a11y + feedback + nav affordances into one UX-baseline pass and kept the
  structural refactor out of scope.
