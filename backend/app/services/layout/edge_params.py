"""Port of graph.js's buildVisEdges (lines 981-1030) and concept-map.js's
similarityToEdgeLength/buildConceptEdges (lines 36-40, 318-386). See those files
for the JS source this must match exactly — golden-tested against
frontend-generated fixtures.
"""

import math
import re

# Human-readable display labels for etymology template types (graph.js lines 261-264).
EDGE_LABELS: dict[str, str] = {
    "inh": "inherited",
    "bor": "borrowed",
    "der": "derived",
    "cog": "cognate",
    "component": "component",
    "mention": "related",
}

_RGBA_RE = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)")


def color_with_opacity(color: str, opacity: float) -> str:
    """Apply an opacity to a hex (#rrggbb) or rgb(a)(...) color string.

    Port of graph.js colorWithOpacity (lines 328-335).
    """
    rgba_match = _RGBA_RE.match(color)
    if rgba_match:
        r, g, b = rgba_match.group(1), rgba_match.group(2), rgba_match.group(3)
        return f"rgba({r},{g},{b},{opacity})"
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return f"rgba({r},{g},{b},{opacity})"


def build_vis_edges(edges: list[dict]) -> list[dict]:
    """Compute vis.js display/physics parameters for etymology graph edges.

    Port of graph.js buildVisEdges (lines 981-1030).

    Args:
        edges: List of {"from": str, "to": str, "label": str} edges.

    Returns:
        Each input edge dict merged with computed rawType/label/arrows/dashes/
        color/length/springConstant fields. The original "label" is overwritten
        with the computed display label.
    """
    # Compute degree (number of connections) per node.
    degree: dict[str, int] = {}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1

    base_length = 110
    length_scale = 50
    base_spring = 0.1

    result = []
    for e in edges:
        is_mention = e["label"] == "component" or e["label"] == "mention"
        d_from = degree.get(e["from"], 1)
        d_to = degree.get(e["to"], 1)
        combined = d_from + d_to
        max_deg = max(d_from, d_to)

        edge_opacity = max(0.2, 1.0 / math.log2(2 + max_deg))
        hide_label = d_from > 5 and d_to > 5

        if e["label"] == "cog":
            base_color = color_with_opacity("#F5C842", edge_opacity)
            highlight_color = "#FFE066"
        elif is_mention:
            base_color = color_with_opacity("#888888", edge_opacity)
            highlight_color = "#aaaaaa"
        else:
            base_color = color_with_opacity("#555555", edge_opacity)
            highlight_color = "#aaaaaa"

        result.append(
            {
                **e,
                "rawType": e["label"],
                "label": "" if hide_label else EDGE_LABELS.get(e["label"], e["label"]),
                "arrows": "to",
                "dashes": e["label"] == "bor" or e["label"] == "cog" or is_mention,
                "color": {"color": base_color, "highlight": highlight_color},
                "length": base_length + length_scale * math.log2(1 + combined),
                "springConstant": base_spring / math.log2(1 + max_deg),
            }
        )
    return result


def similarity_to_edge_length(similarity: float) -> float:
    """Map a phonetic similarity score (0-1) to an inverse edge length.

    Port of concept-map.js similarityToEdgeLength (lines 36-40).
    """
    min_length = 50
    max_length = 250
    return max_length - (similarity * (max_length - min_length))


def build_concept_edges(
    phonetic_edges: list[dict], etym_edges: list[dict], include_etymology_edges: bool
) -> list[dict]:
    """Compute vis.js display/physics parameters for concept-map edges.

    Port of concept-map.js buildConceptEdges (lines 318-386). The JS reads the
    "show-etymology-edges" checkbox directly from the DOM; the server-side port
    takes that as the explicit `include_etymology_edges` parameter instead.

    Args:
        phonetic_edges: [{"source": str, "target": str, "similarity": float,
            "turchin_match": bool}].
        etym_edges: [{"source": str, "target": str, "relationship": str}].
        include_etymology_edges: Whether to include etym_edges in the output
            (and in the degree computation used for phonetic edge lengths).

    Returns:
        List of vis.js edge dicts: phonetic edges first (in input order),
        followed by etymology edges (in input order) if included.
    """
    # Compute degree (number of connections) per node across all edge types.
    degree: dict[str, int] = {}
    for e in phonetic_edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    if include_etymology_edges:
        for e in etym_edges:
            degree[e["source"]] = degree.get(e["source"], 0) + 1
            degree[e["target"]] = degree.get(e["target"], 0) + 1

    base_spring = 0.008
    vis_edges = []

    # Phonetic similarity edges: dashed grey.
    for e in phonetic_edges:
        similarity = e["similarity"]
        opacity = max(0.2, similarity)
        width = 0.35 + 1.5 * similarity
        d_from = degree.get(e["source"], 1)
        d_to = degree.get(e["target"], 1)
        combined = d_from + d_to
        max_deg = max(d_from, d_to)
        base_length = similarity_to_edge_length(similarity)
        pct = f"{similarity * 100:.0f}"
        title = f"{pct}% similar"
        if e.get("turchin_match"):
            title += " (Turchin match)"
        vis_edges.append(
            {
                "from": e["source"],
                "to": e["target"],
                "dashes": [5, 5],
                "color": {
                    "color": f"rgba(180,180,200,{opacity})",
                    "highlight": f"rgba(200,200,220,{opacity + 0.2})",
                },
                "width": width,
                "length": base_length + 40 * math.log2(1 + combined),
                "springConstant": base_spring / math.log2(1 + max_deg),
                "title": title,
                "edgeType": "phonetic",
            }
        )

    # Etymology edges: solid, color-coded by relationship type.
    if include_etymology_edges:
        for e in etym_edges:
            d_from = degree.get(e["source"], 1)
            d_to = degree.get(e["target"], 1)
            combined = d_from + d_to
            max_deg = max(d_from, d_to)
            is_cognate = e["relationship"] == "cognate"
            edge_color = (
                {"color": "rgba(245,200,66,0.7)", "highlight": "rgba(245,200,66,1)"}
                if is_cognate
                else {
                    "color": "rgba(180,180,200,0.25)",
                    "highlight": "rgba(220,220,240,0.5)",
                }
            )
            vis_edges.append(
                {
                    "from": e["source"],
                    "to": e["target"],
                    "dashes": False,
                    "color": edge_color,
                    "width": 2.5 if is_cognate else 0.8,
                    "arrows": "to",
                    "length": 120 + 40 * math.log2(1 + combined),
                    "springConstant": base_spring / math.log2(1 + max_deg),
                    "title": e.get("relationship") or "etymological",
                    "edgeType": "etymology",
                }
            )

    return vis_edges
