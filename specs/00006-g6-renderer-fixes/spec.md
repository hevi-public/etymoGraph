# SPC-00006: G6 Renderer Fixes (Physics, Spacing, Trackpad)

| Field | Value |
|---|---|
| **Status** | implemented |
| **Created** | 2026-02-11 |
| **Modifies** | SPC-00005 (fixes G6 renderer UX: physics animation, force spacing, trackpad interaction) |
| **Modified-by** | — |

## Summary

Three targeted fixes to the G6 v5 experimental renderer introduced in SPC-00005, all scoped to `frontend/public/js/g6-adapter.js`.

## Fix 1: Animated Force Simulation

**Problem:** The `d3-force` layout computed all node positions in one pass and rendered the final state instantly. The graph felt static compared to vis.js's continuous physics loop.

**Solution:**
- Add `animate: true` to the layout config so G6 renders intermediate positions each tick
- Add `iterations: 300` for enough simulation steps to settle
- Replace `"drag-element"` behavior with `"drag-element-force"` so dragging a node triggers real-time force recalculation (nearby nodes push away)

## Fix 2: Tuned Force Parameters

**Problem:** Default force parameters produced a dense cluster with overlapping labels.

**Solution:** Increase repulsion strength and spacing distances:

| Parameter | Before | After |
|---|---|---|
| `nodeSize` | 40 | 50 |
| `link.distance` | 150 | 200 |
| `charge.strength` | -300 | -500 |
| `charge.distanceMax` | 600 | 800 |
| `collide.radius` | 30 | 50 |
| `collide.strength` | 0.7 | 0.8 |

## Fix 3: macOS Trackpad Pan + Pinch Zoom

**Problem:** G6's `zoom-canvas` behavior mapped all wheel events to zoom. On macOS trackpads, two-finger scroll (which fires wheel events with `ctrlKey: false`) should pan, and pinch gestures (wheel events with `ctrlKey: true`) should zoom. Both were triggering zoom.

**Solution:**
- Replace `"zoom-canvas"` with `"scroll-canvas"` in the behaviors array — this makes two-finger scroll pan the canvas in all directions
- Add a custom `wheel` event listener on the container that intercepts only `ctrlKey: true` events (pinch gestures) and applies zoom via `graph.getZoom()` / `graph.zoomTo()`
- This mirrors the trackpad handling pattern used in the vis.js renderer (`graph.js:686-704`)

## Files Changed

| File | Changes |
|---|---|
| `frontend/public/js/g6-adapter.js` | Layout config (animate, tuned forces), behaviors (drag-element-force, scroll-canvas), custom pinch-to-zoom handler |

## Verification

1. Load `/?renderer=g6&word=wine` — nodes animate into position over ~2 seconds
2. Graph is well-spread with readable labels (not a dense cluster)
3. Drag a node — nearby nodes push away in real-time
4. Two-finger scroll pans in all directions
5. Pinch gesture zooms in/out smoothly
6. Load `/?renderer=g6&word=water` — large graph settles and remains readable
7. vis.js renderer unaffected by changes
