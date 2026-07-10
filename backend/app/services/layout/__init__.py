"""Server-side graph layout engine (SPC-00021): a numpy FA2-style solver
seeded by a faithful port of the client's deterministic layout engine
(frontend/public/js/graph.js / concept-map.js).

Bump LAYOUT_ALGO_VERSION whenever a solver/seeding formula changes — it's
part of the `layouts` cache key, so a bump invalidates old cache entries and
signals that golden/characterization snapshots need regenerating.
"""

from app.services.layout.edge_params import (
    build_concept_edges,
    build_vis_edges,
    color_with_opacity,
    similarity_to_edge_length,
)
from app.services.layout.families import (
    ERA_TIERS,
    LANG_FAMILIES,
    assign_family_cluster_positions,
    build_extra_edges,
    classify_lang,
    get_era_tier,
    get_lang_family,
    group_nodes_by_tier_and_family,
)
from app.services.layout.phonetic_numpy import build_similarity_edges_vectorized
from app.services.layout.seed import compute_tree_positions

# "2": etymology layouts switched from the base constant-magnitude central
# gravity to vis's ForceAtlas2BasedCentralGravitySolver law (SPC-00021).
# "3": concept layout switched from the FA2 repulsion law to vis's barnesHut
# 1/d² law its G=-8000 was calibrated for — under FA2's 1/d law every concept
# solve exploded to a velocity-clamp-limited square (SPC-00021 Phase 5).
LAYOUT_ALGO_VERSION = "3"

__all__ = [
    "ERA_TIERS",
    "LANG_FAMILIES",
    "LAYOUT_ALGO_VERSION",
    "assign_family_cluster_positions",
    "build_concept_edges",
    "build_extra_edges",
    "build_similarity_edges_vectorized",
    "build_vis_edges",
    "classify_lang",
    "color_with_opacity",
    "compute_tree_positions",
    "get_era_tier",
    "get_lang_family",
    "group_nodes_by_tier_and_family",
    "similarity_to_edge_length",
]
