# Bug Report: Clicking a different node while one is selected doesn't work correctly

| Field | Value |
|---|---|
| **Reporter** | User |
| **Date** | 2026-02-11 |
| **Severity** | High |
| **Component** | G6 etymology graph renderer (`g6-adapter.js`) |
| **Related specs** | SPC-00009 (highlight/dim) |
| **Related bugs** | bug-002 (canvas click deselect) — likely same root cause |
| **Status** | Open |

## Description

In the G6 renderer, after selecting a node (which applies hop-based highlight/dim), clicking on a different node does not correctly select the new node. The behavior is broken — either the wrong node gets selected, or the click doesn't register properly.

## Steps to Reproduce

1. Navigate to `/?word=wine&renderer=g6`
2. Wait for the graph to settle
3. Click on a node (e.g., "vin (French)") — highlight/dim applies correctly
4. Click on a different node (e.g., "vino (Spanish)")
5. Expected: highlight recalculates from the new node, detail panel shows new node
6. Actual: incorrect behavior — wrong node selected or click not registered

## Expected Behavior

Clicking any node while another is highlighted should:
1. Recalculate hop distances from the newly clicked node
2. Update the highlight/dim states accordingly
3. Show the detail panel for the newly clicked node
4. Animate focus to the newly clicked node

## Root Cause (Investigation Needed)

Likely related to bug-002 (canvas click not deselecting). Probable causes:

1. **`drag-element-force` behavior interference**: This behavior handles drag events on nodes during force layout. It may be intercepting the click event or misrouting it when nodes have opacity states applied.

2. **Hit-testing on faded nodes**: When nodes are in `faded` state (opacity 0.1), G6's hit-testing may not detect them as click targets, or may detect a different element.

3. **`focusElement` animation conflict**: After `_applyHighlight(nodeId)` runs, the `focusElement` animation shifts the viewport. If the user clicks during or right after a focus animation, the click coordinates may map to the wrong node.

4. **`event.target.id` stale reference**: G6 may return the previously focused/selected node's ID instead of the actually clicked node when states are active.

## Possible Fixes

1. Log `event.target.id` in the click handler to confirm which node ID G6 reports
2. Try using `event.target` differently (e.g., `event.itemId` or `event.targetType`)
3. Clear all states before re-applying highlight to avoid hit-testing interference
4. Consider using `canvas:pointerup` + manual hit testing as a workaround for all click-related bugs (bug-002 and bug-003)
