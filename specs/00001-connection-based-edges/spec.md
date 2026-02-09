# SPC-00001: Connection-Based Edge Length & Strength

| Field | Value |
|---|---|
| **Status** | implemented |
| **Created** | 2026-02-08 |
| **Modifies** | — |
| **Modified-by** | — |

---

## Problem

Dense clusters (e.g., Latin/Romance around "circle") collapse into unreadable blobs,
while lone links (e.g., "sèk (Haitian Creole)" with 1-2 connections) float too far away.

**Root cause:** All edges share global physics (`length: 200`, `springConstant: 0.05`)
with no per-edge customization.

## Approaches Evaluated

### A: Length-Only

Scale edge `length` by endpoint degree; keep `springConstant` global.

```
length = BASE_LENGTH + LENGTH_SCALE * log2(1 + dFrom + dTo)
```

- Pros: Simple, easy to tune
- Cons: Dense hubs still compress under uniform spring force

### B: Log-Degree Combined (Chosen)

Scale both `length` and `springConstant` per-edge using log2 of endpoint degrees.

```
length        = BASE_LENGTH + LENGTH_SCALE * log2(1 + dFrom + dTo)
springConstant = BASE_SPRING / log2(1 + max(dFrom, dTo))
```

Parameters (updated for dense cluster readability):
- `BASE_LENGTH = 180` (minimum edge rest length)
- `LENGTH_SCALE = 80` (how much degree adds to length)
- `BASE_SPRING = 0.08` (spring constant for degree-1 nodes)

- Pros: Dense clusters spread out (longer + weaker springs), peripheral nodes pulled closer (shorter + stronger springs)
- Cons: Slightly more complex; two parameters to tune

### C: Linear Combined

Same as B but using linear degree instead of log2.

```
length        = BASE_LENGTH + LENGTH_SCALE * (dFrom + dTo)
springConstant = BASE_SPRING / max(dFrom, dTo)
```

- Pros: Stronger separation for very dense hubs
- Cons: Overly aggressive — large graphs become too spread out; high-degree nodes get near-zero spring force causing instability

## Decision

**Approach B** — log-degree dampens the scaling enough to avoid instability while still providing meaningful separation for dense clusters. The logarithmic curve ensures that going from 1 to 5 connections has a bigger visual impact than going from 20 to 25, which matches perceptual importance.

## Dense Cluster Readability (Phase 2)

The initial log-degree scaling improved peripheral placement but dense centers (60+ nodes) remained visually cluttered. Two additional techniques address this:

### Physics Tuning (force-directed layout)

| Parameter | Original | Updated | Why |
|-----------|----------|---------|-----|
| `gravitationalConstant` | -120 | -200 | Stronger repulsion pushes dense center apart |
| `centralGravity` | 0.01 | 0.005 | Halved — with many nodes it compounds and compresses |
| `springConstant` | 0.05 | 0.04 | Softer springs let repulsion win locally |
| `damping` | 0.7 | 0.6 | Less friction helps layout escape local minima |
| `avoidOverlap` | (absent) | 0.5 | Collision avoidance based on node bounding box |

### Degree-Based Edge Opacity

Edges between high-degree nodes fade; peripheral edges stay vivid:

```
edgeOpacity = max(0.2, 1.0 / log2(2 + maxDeg))
```

| maxDeg | edgeOpacity |
|--------|-------------|
| 1 | 0.63 |
| 3 | 0.40 |
| 5 | 0.36 |
| 10 | 0.28 |
| 15+ | 0.20 (floor) |

Applied to all edge types (default grey, cognate gold, mention grey). Highlight colors stay bright — only resting color fades. On node click, hop-based brightness multiplies with degree opacity for compound fading.

### Label Hiding in Dense Areas

When both endpoints have degree > 5, edge labels are hidden (they overlap and are unreadable). Edge type is still conveyed by line style (solid vs dashed) and color (gold for cognate).

## Scope

- Etymology graph: `buildVisEdges()` in `graph.js`
- Concept map: `buildConceptEdges()` in `concept-map.js` (degree factor applied to similarity-based lengths)
- Both force-directed and era-layered layouts benefit since per-edge properties override global physics
