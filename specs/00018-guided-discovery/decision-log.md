# Decision Log: SPC-00018 Guided Discovery

## Starting Question

The app starts cold on *wine* with no discovery path. What's the lightest set of entry points that
gives hobbyists a reason to explore (and return) without adding accounts, tracking, or heavy
infrastructure?

## Alternatives Considered

### Option A: Pure random button only
- **Pros:** Trivial.
- **Cons:** Random entries are often dead ends (no ancestry, obscure forms). Discovery quality is
  poor; no sense of curation or return value.

### Option B: Editorialized feed / CMS
- **Pros:** Maximum quality and narrative.
- **Cons:** Heavy; needs ongoing human content work; against the local, no-backend-state ethos.

### Option C: Curated pools + smart random + tours + data-driven "did you know" (chosen)
A small curated store (word-of-the-day pool, tour lists) combined with a *quality-filtered* random
sampler and "did you know" cards generated from the doublets/borrowing data.
- **Pros:** Good quality with minimal content upkeep; smart-random avoids dead ends; "did you know"
  is data-driven (reuses SPC-00015), so it scales without editorial effort; fits the local ethos.
- **Cons:** Needs a small curated dataset and a sampling endpoint.

## Decision & Rationale

**Option C.** It balances curation quality against maintenance cost: a tiny hand-curated layer
(tours + word-of-the-day pool) plus data-driven generation (smart random, did-you-know from
doublets) gives a rich experience without a CMS. Quiz/game mode is deferred so this spec stays
focused on the on-ramp; it can reuse these endpoints later.

### Sub-decision: deterministic word of the day
Seed the daily pick by date (no randomness at request time) so the choice is stable across reloads
and shareable — consistent with the app's deterministic-by-default posture (cf. the fixed graph
seed).

## Participants

- **Human:** Asked for a toolset great for hobbyists as well as linguists.
- **Claude (DA):** Proposed a curation-light, data-driven discovery layer and deferred quiz mode.
