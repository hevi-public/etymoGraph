"""Port of graph.js's tree-position seeding engine (lines 415-644): BFS
spanning tree -> radial (etymology, has levels) or linear (concept map, no
levels) positions -> barycentric refinement using ALL edges (not just the
spanning tree) -> disconnected-node fan placement.
"""

import math
from collections import deque

TREE_LEVEL_SPACING: float = 110
TREE_SIBLING_SPACING: float = 90

RADIAL_MIN_ANGLE: float = 0.1  # Minimum angular span per leaf (radians)
RADIAL_RING_SPACING: float = 110  # Pixels between concentric rings


def compute_linear_tree_positions(
    children: dict[str, list[str]],
    node_map: dict[str, dict],
    bfs_depth: dict[str, int],
    root_id: str,
) -> dict[str, dict[str, float]]:
    """Compute linear tree positions: siblings fan out horizontally under their parent.

    Used for concept maps (no level data) where a top-down tree shape is
    appropriate. Port of graph.js computeLinearTreePositions (lines 427-461).

    Args:
        children: parentId -> [childIds] from BFS spanning tree.
        node_map: nodeId -> node dict.
        bfs_depth: nodeId -> BFS depth from root.
        root_id: ID of the root node.

    Returns:
        Node ID to {"x", "y"} position mapping.
    """
    subtree_width: dict[str, float] = {}

    def compute_width(node_id: str) -> float:
        kids = children.get(node_id) or []
        if len(kids) == 0:
            subtree_width[node_id] = TREE_SIBLING_SPACING
            return subtree_width[node_id]
        total = 0
        for kid in kids:
            total += compute_width(kid)
        subtree_width[node_id] = total
        return total

    compute_width(root_id)

    positions: dict[str, dict[str, float]] = {}

    def assign_positions(node_id: str, x_center: float) -> None:
        node = node_map.get(node_id)
        level = node.get("level") if node is not None else None
        if level is None:
            level = bfs_depth.get(node_id, 0)
        positions[node_id] = {"x": x_center, "y": level * TREE_LEVEL_SPACING}

        kids = children.get(node_id) or []
        if len(kids) == 0:
            return

        total_width = subtree_width[node_id]
        x_start = x_center - total_width / 2
        for kid in kids:
            kid_width = subtree_width[kid]
            assign_positions(kid, x_start + kid_width / 2)
            x_start += kid_width

    assign_positions(root_id, 0)
    return positions


def compute_radial_positions(
    children: dict[str, list[str]],
    node_map: dict[str, dict],  # noqa: ARG001 (unused, kept for signature parity with graph.js)
    bfs_depth: dict[str, int],
    root_id: str,
) -> dict[str, dict[str, float]]:
    """Compute radial tree positions: nodes fan in concentric rings from root.

    Matches the radial shape that forceAtlas2Based converges to, so physics
    only fine-tunes rather than rearranges. Port of graph.js
    computeRadialPositions (lines 476-522).

    Args:
        children: parentId -> [childIds] from BFS spanning tree.
        node_map: nodeId -> node dict.
        bfs_depth: nodeId -> BFS depth from root.
        root_id: ID of the root node.

    Returns:
        Node ID to {"x", "y"} position mapping.
    """
    # Bottom-up: compute angular span per subtree.
    angular_span: dict[str, float] = {}

    def compute_span(node_id: str) -> float:
        kids = children.get(node_id) or []
        if len(kids) == 0:
            angular_span[node_id] = RADIAL_MIN_ANGLE
            return RADIAL_MIN_ANGLE
        total = 0
        for kid in kids:
            total += compute_span(kid)
        angular_span[node_id] = total
        return total

    compute_span(root_id)

    # Top-down: assign polar coordinates then convert to cartesian.
    positions: dict[str, dict[str, float]] = {}
    positions[root_id] = {"x": 0, "y": 0}

    def assign_radial(node_id: str, angle_start: float, angle_end: float) -> None:
        kids = children.get(node_id) or []
        if len(kids) == 0:
            return

        parent_span = angular_span[node_id]
        cursor = angle_start

        for kid in kids:
            kid_fraction = angular_span[kid] / parent_span
            kid_angle_start = cursor
            kid_angle_end = cursor + (angle_end - angle_start) * kid_fraction
            kid_angle = (kid_angle_start + kid_angle_end) / 2

            depth = bfs_depth.get(kid) or 1
            radius = depth * RADIAL_RING_SPACING
            positions[kid] = {
                "x": radius * math.cos(kid_angle),
                "y": radius * math.sin(kid_angle),
            }

            assign_radial(kid, kid_angle_start, kid_angle_end)
            cursor = kid_angle_end

    assign_radial(root_id, 0, 2 * math.pi)
    return positions


def apply_barycentric_refinement(
    positions: dict[str, dict[str, float]],
    nodes: list[dict],
    edges: list[dict],
    root_id: str,
    iterations: int = 3,
) -> None:
    """Shift non-fixed nodes toward the barycenter of their neighbors.

    Uses ALL edges (not just the spanning tree), so cognates, borrowings, and
    mentions that the tree layout ignores still pull node positions. Mutates
    `positions` in place, matching the JS function's own signature/behavior.
    Port of graph.js applyBarycentricRefinement (lines 534-564).

    Args:
        positions: Mutable node ID to {"x", "y"} position mapping.
        nodes: List of node dicts (each with an "id").
        edges: Full edge list (all relationship types), each with "from"/"to".
        root_id: Fixed root node ID (excluded from refinement).
        iterations: Number of refinement passes.
    """
    # Build full adjacency list from ALL edges.
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["from"] in adj:
            adj[e["from"]].append(e["to"])
        if e["to"] in adj:
            adj[e["to"]].append(e["from"])

    damping = 0.5

    for _iter in range(iterations):
        for n in nodes:
            if n["id"] == root_id:
                continue  # Root stays fixed at (0,0)
            neighbors = adj.get(n["id"]) or []
            if len(neighbors) == 0:
                continue

            sum_x = 0
            sum_y = 0
            count = 0
            for nid in neighbors:
                pos = positions.get(nid)
                if pos:
                    sum_x += pos["x"]
                    sum_y += pos["y"]
                    count += 1
            if count == 0:
                continue

            cur = positions.get(n["id"])
            if not cur:
                continue
            cur["x"] += (sum_x / count - cur["x"]) * damping
            cur["y"] += (sum_y / count - cur["y"]) * damping


def compute_tree_positions(  # noqa: PLR0912 (faithful line-for-line port of graph.js; not split up)
    nodes: list[dict], edges: list[dict], root_id: str | None
) -> dict[str, dict[str, float]]:
    """Compute tree-based initial positions for force-directed layout.

    BFS from root discovers parent-child relationships. Then:
    - Etymology graphs (nodes have levels) -> radial ring layout
    - Concept maps (no levels) -> linear top-down tree layout
    Both get barycentric refinement to account for non-tree edges.
    Port of graph.js computeTreePositions (lines 577-644).

    Args:
        nodes: List of {"id": str, "level": int | None} node dicts.
        edges: List of {"from": str, "to": str} edge dicts.
        root_id: ID of the root node.

    Returns:
        Node ID to {"x", "y"} position mapping.
    """
    if not nodes or not root_id:
        return {}
    if not edges:
        return {root_id: {"x": 0, "y": 0}}

    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # Build undirected adjacency list. Insertion order matters: it determines
    # BFS neighbor visitation order, which determines children[] order, which
    # determines the whole tree shape.
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        if e["from"] in adj:
            adj[e["from"]].append(e["to"])
        if e["to"] in adj:
            adj[e["to"]].append(e["from"])

    # BFS from root to discover parent-child spanning tree.
    children: dict[str, list[str]] = {}
    bfs_depth: dict[str, int] = {}
    visited: set[str] = set()
    queue: deque[str] = deque([root_id])
    visited.add(root_id)
    bfs_depth[root_id] = 0

    while queue:
        cur = queue.popleft()
        if cur not in children:
            children[cur] = []
        for neighbor in adj.get(cur) or []:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            bfs_depth[neighbor] = bfs_depth[cur] + 1
            children[cur].append(neighbor)
            queue.append(neighbor)

    # Detect graph type: etymology graphs always have level data.
    has_levels = any(n.get("level") is not None for n in nodes)

    if has_levels:
        positions = compute_radial_positions(children, node_map, bfs_depth, root_id)
    else:
        positions = compute_linear_tree_positions(children, node_map, bfs_depth, root_id)

    # Place disconnected nodes in a fan beyond the positioned nodes.
    unvisited = [n for n in nodes if n["id"] not in visited]
    if unvisited:
        all_pos = list(positions.values())
        max_r = max(math.sqrt(p["x"] * p["x"] + p["y"] * p["y"]) for p in all_pos) if all_pos else 0
        fan_radius = max_r + TREE_SIBLING_SPACING * 2
        angle_step = (2 * math.pi) / max(len(unvisited), 1)
        for i, n in enumerate(unvisited):
            angle = i * angle_step
            positions[n["id"]] = {
                "x": fan_radius * math.cos(angle),
                "y": fan_radius * math.sin(angle),
            }

    # Barycentric refinement: shift nodes toward neighbors across ALL edges.
    apply_barycentric_refinement(positions, nodes, edges, root_id)

    return positions
