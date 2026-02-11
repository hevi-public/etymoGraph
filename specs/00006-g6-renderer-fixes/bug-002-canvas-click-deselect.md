# Bug Report: Cannot deselect node by clicking canvas background

| Field | Value |
|---|---|
| **Reporter** | User |
| **Date** | 2026-02-11 |
| **Severity** | Medium |
| **Component** | G6 etymology graph renderer (`g6-adapter.js`) |
| **Related specs** | SPC-00009 (highlight/dim) |
| **Status** | Open |

## Description

After selecting a node in the G6 etymology graph (which correctly applies hop-based highlight/dim), clicking on the canvas background does not clear the highlight states. Nodes remain dimmed until a different node is clicked.

## Steps to Reproduce

1. Navigate to `/?word=wine&renderer=g6`
2. Wait for the graph to settle
3. Click on a node (e.g., "vin (French)") — neighbors highlight, distant nodes dim
4. Click on empty canvas area (no node)
5. Expected: all nodes return to full opacity
6. Actual: highlight/dim states remain applied

## Expected Behavior

Clicking the canvas background should reset all node and edge states to default (full opacity), matching the vis.js behavior.

## Root Cause (Investigation Needed)

The `canvas:click` handler in `g6-adapter.js` calls `_clearAllStates()` which calls `graph.setElementState(stateMap)` with empty arrays for all elements. The E2E test passes (states are cleared programmatically via `graph.emit("canvas:click")`), so the issue may be:

1. G6's canvas click detection not firing for actual mouse clicks (possible if the `drag-canvas` behavior consumes the click event)
2. The `drag-canvas` behavior may interpret short clicks as drag-starts and suppress the `canvas:click` event
3. Hit testing: G6 may detect a node under the cursor even in "empty" areas due to node bounding box size

## Possible Fixes

1. Register a DOM-level click handler on the container element as a fallback
2. Debounce or check if the click was on a node before treating it as a canvas click
3. Adjust the `drag-canvas` behavior configuration to not suppress click events
4. Use `canvas:pointerup` instead of `canvas:click` if drag-canvas suppresses click
