# Bug Report: Cannot click nodes during physics animation

| Field | Value |
|---|---|
| **Reporter** | User |
| **Date** | 2026-02-11 |
| **Severity** | Medium |
| **Component** | G6 etymology graph renderer (`g6-adapter.js`) |
| **Related specs** | SPC-00005, SPC-00006, SPC-00009 |
| **Status** | Open |

## Description

In the G6 renderer, when the physics simulation is still running (nodes are moving/settling), clicking on a node does not trigger the click handler. The user must wait for the layout animation to fully settle before they can interact with nodes.

## Steps to Reproduce

1. Navigate to `/?word=wine&renderer=g6`
2. While the nodes are still animating (moving into position over ~2 seconds), click on any node
3. Expected: node click triggers detail panel + highlight/dim
4. Actual: nothing happens — the click is not registered

## Expected Behavior

Node clicks should work during the physics animation, same as vis.js where nodes are clickable at any time.

## Root Cause (Investigation Needed)

Likely caused by the G6 `drag-element-force` behavior intercepting click events during the force layout animation, or the d3-force layout consuming pointer events during active simulation. The node positions are changing each tick, which may cause hit-testing to miss the node.

## Possible Fixes

1. Ensure G6's click handler is registered before the force layout starts
2. Use `graph.on("node:click")` with a broader hit area during animation
3. Reduce animation speed so nodes settle faster
4. Add a click buffer that retries the hit test if the force layout is active
