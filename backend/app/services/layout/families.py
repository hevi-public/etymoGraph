"""Port of graph.js's language-family classification and era-tier machinery
(lines 196-226, 350-374, 378-413, 795-817). See that file for the JS source
this must match exactly — golden-tested against frontend-generated fixtures.
"""

import re

# Single source of truth for language family classification: (family_id, display_name,
# color, compiled_pattern). Ordered by general frequency in etymology graphs (most
# common first). Patterns are unanchored substring searches (JS regex.test() without
# ^/$ behaves like Python's re.search()), case-insensitive.
LANG_FAMILIES: list[tuple[str, str, str, re.Pattern]] = [
    (
        "germanic",
        "Germanic",
        "#5B8DEF",
        re.compile(
            r"english|german|norse|dutch|frisian|gothic|proto-germanic|"
            r"proto-west germanic|saxon|scots|yiddish|afrikaans|plautdietsch|"
            r"limburgish|luxembourgish|cimbrian|alemannic|bavarian|vilamovian|"
            r"saterland|icelandic|faroese|norwegian|swedish|danish",
            re.IGNORECASE,
        ),
    ),
    (
        "romance",
        "Romance",
        "#EF5B5B",
        re.compile(
            r"latin|italic|french|spanish|portuguese|romanian|proto-italic|"
            r"catalan|occitan|sardinian|galician|venetian|sicilian|neapolitan|"
            r"asturian|aragonese|friulian|ladin|romansch|aromanian|dalmatian",
            re.IGNORECASE,
        ),
    ),
    ("greek", "Greek", "#43D9A2", re.compile(r"greek", re.IGNORECASE)),
    ("pie", "PIE", "#F5C842", re.compile(r"proto-indo-european", re.IGNORECASE)),
    (
        "slavic",
        "Slavic",
        "#CE6BF0",
        re.compile(
            r"russian|polish|czech|slovak|serbian|croatian|bulgarian|ukrainian|"
            r"slovene|proto-slavic|old church slavonic|belarusian|macedonian|"
            r"sorbian|rusyn|kashubian",
            re.IGNORECASE,
        ),
    ),
    (
        "celtic",
        "Celtic",
        "#FF8C42",
        re.compile(
            r"irish|welsh|scottish gaelic|breton|cornish|manx|proto-celtic|"
            r"old irish|gaulish|celtiberian|galatian",
            re.IGNORECASE,
        ),
    ),
    (
        "indoiranian",
        "Indo-Iranian",
        "#FF6B9D",
        re.compile(
            r"sanskrit|hindi|persian|urdu|bengali|punjabi|avestan|pali|"
            r"proto-indo-iranian|farsi|dari|tajik|pashto|kurdish|balochi|"
            r"marathi|gujarati|nepali|sinhalese|romani|ossetian|sogdian|bactrian",
            re.IGNORECASE,
        ),
    ),
    (
        "semitic",
        "Semitic",
        "#00BCD4",
        re.compile(
            r"arabic|hebrew|aramaic|akkadian|proto-semitic|amharic|tigrinya|"
            r"maltese|phoenician|ugaritic|ge'ez|syriac",
            re.IGNORECASE,
        ),
    ),
    (
        "uralic",
        "Uralic",
        "#8BC34A",
        re.compile(
            r"finnish|hungarian|estonian|proto-uralic|proto-finnic|sami|"
            r"karelian|veps|mari|mordvin|udmurt|komi|mansi|khanty|nenets|selkup",
            re.IGNORECASE,
        ),
    ),
    (
        "baltic",
        "Baltic",
        "#FFC107",
        re.compile(
            r"lithuanian|latvian|proto-baltic|proto-balto-slavic|old prussian|samogitian",
            re.IGNORECASE,
        ),
    ),
    (
        "turkic",
        "Turkic",
        "#673AB7",
        re.compile(
            r"turkish|ottoman|azerbaijani|kazakh|uzbek|uyghur|turkmen|kyrgyz|"
            r"tatar|bashkir|chuvash|proto-turkic|gagauz|crimean tatar|yakut",
            re.IGNORECASE,
        ),
    ),
    (
        "sinotibetan",
        "Sino-Tibetan",
        "#9C27B0",
        re.compile(
            r"chinese|mandarin|cantonese|tibetan|burmese|proto-sino-tibetan|"
            r"middle chinese|old chinese|wu|min|hakka|shanghainese|hokkien",
            re.IGNORECASE,
        ),
    ),
    (
        "austronesian",
        "Austronesian",
        "#2196F3",
        re.compile(
            r"indonesian|malay|tagalog|javanese|proto-austronesian|hawaiian|"
            r"maori|samoan|tongan|fijian|cebuano|ilocano|sundanese|malagasy|"
            r"chamorro|rapanui",
            re.IGNORECASE,
        ),
    ),
    (
        "japonic",
        "Japonic",
        "#E91E63",
        re.compile(
            r"japanese|proto-japonic|okinawan|ryukyuan|old japanese",
            re.IGNORECASE,
        ),
    ),
    (
        "koreanic",
        "Koreanic",
        "#607D8B",
        re.compile(
            r"korean|proto-koreanic|middle korean|old korean|jeju",
            re.IGNORECASE,
        ),
    ),
    (
        "bantu",
        "Bantu",
        "#795548",
        re.compile(
            r"swahili|zulu|xhosa|yoruba|igbo|proto-bantu|lingala|shona|"
            r"kikuyu|luganda|kinyarwanda|setswana|sesotho|chichewa",
            re.IGNORECASE,
        ),
    ),
    (
        "dravidian",
        "Dravidian",
        "#009688",
        re.compile(
            r"tamil|telugu|malayalam|kannada|proto-dravidian|brahui|tulu|gondi",
            re.IGNORECASE,
        ),
    ),
    (
        "kartvelian",
        "Kartvelian",
        "#4CAF50",
        re.compile(
            r"georgian|mingrelian|svan|laz|proto-kartvelian|old georgian",
            re.IGNORECASE,
        ),
    ),
    (
        "armenian",
        "Armenian",
        "#FF5722",
        re.compile(
            r"armenian|proto-armenian|classical armenian|old armenian",
            re.IGNORECASE,
        ),
    ),
    (
        "albanian",
        "Albanian",
        "#CDDC39",
        re.compile(r"albanian|proto-albanian|gheg|tosk", re.IGNORECASE),
    ),
]

DEFAULT_FAMILY_COLOR = "#A0A0B8"

# Era tier definitions (used by the era-layered layout strategy).
# En dashes below are verbatim from the JS source's display strings (date ranges) —
# preserved exactly for fidelity rather than normalized to hyphens.
ERA_TIERS: list[dict] = [
    {"name": "Deep Proto", "date": "~4000+ BCE", "y": 800},
    {"name": "Branch Proto", "date": "~2000–500 BCE", "y": 650},  # noqa: RUF001
    {"name": "Classical/Ancient", "date": "~500 BCE–500 CE", "y": 500},  # noqa: RUF001
    {"name": "Early Medieval", "date": "~500–1000 CE", "y": 350},  # noqa: RUF001
    {"name": "Late Medieval", "date": "~1000–1500 CE", "y": 200},  # noqa: RUF001
    {"name": "Early Modern", "date": "~1500–1700 CE", "y": 50},  # noqa: RUF001
    {"name": "Modern", "date": "~1700–present", "y": -100},  # noqa: RUF001
    {"name": "Contemporary", "date": "recent", "y": -250},
]

DEEP_PROTO = re.compile(
    r"^Proto-(Indo-European|Uralic|Afro-Asiatic|Sino-Tibetan|Austronesian|"
    r"Niger-Congo|Trans-New Guinea|Dravidian|Turkic|Mongolic|Japonic|Koreanic|"
    r"Tai|Austroasiatic|Nilo-Saharan)$",
    re.IGNORECASE,
)
CLASSICAL_SPECIFIC = re.compile(
    r"^(Latin|Sanskrit|Avestan|Gothic|Akkadian|Sumerian|Tocharian [AB]|Pali|"
    r"Oscan|Umbrian|Mycenaean Greek|Hittite|Luwian|Lydian|Lycian|Sogdian|"
    r"Bactrian|Prakrit|Elamite)$",
    re.IGNORECASE,
)
_ANCIENT_CLASSICAL_BIBLICAL = re.compile(r"^(Ancient |Classical |Biblical )")
_OLD_PREFIX = re.compile(r"^Old ")
_MIDDLE_OR_ANGLO_NORMAN = re.compile(r"^Middle |^Anglo-Norman$", re.IGNORECASE)
_EARLY_MODERN_PREFIX = re.compile(r"^Early Modern ")
_PROTO_PREFIX = re.compile(r"^Proto-")


def classify_lang(lang: str) -> dict:
    """Classify a language name into its family and legend color.

    Args:
        lang: Language display name (e.g. "Old English").

    Returns:
        Dict with "family" (family id string) and "color" (hex string).
    """
    for family, _display_name, color, pattern in LANG_FAMILIES:
        if pattern.search(lang):
            return {"family": family, "color": color}
    return {"family": "other", "color": DEFAULT_FAMILY_COLOR}


def get_lang_family(lang: str) -> str:
    """Return just the family id for a language name."""
    return classify_lang(lang)["family"]


def get_era_tier(lang: str | None) -> int:
    """Classify a language name into an era tier index (0 = deepest proto, 6 = default).

    Args:
        lang: Language display name, or None/empty for unknown.

    Returns:
        Integer tier index, 0-6.
    """
    if not lang:
        return 6

    # Ordered (pattern, tier) checks, mirroring the JS if-chain exactly.
    tier_checks: list[tuple[re.Pattern, int]] = [
        (DEEP_PROTO, 0),
        (_PROTO_PREFIX, 1),
        (_ANCIENT_CLASSICAL_BIBLICAL, 2),
        (CLASSICAL_SPECIFIC, 2),
        (_OLD_PREFIX, 3),
        (_MIDDLE_OR_ANGLO_NORMAN, 4),
        (_EARLY_MODERN_PREFIX, 5),
    ]
    for pattern, tier in tier_checks:
        if pattern.search(lang):
            return tier
    return 6


def group_nodes_by_tier_and_family(nodes: list[dict]) -> dict[int, dict[str, list[str]]]:
    """Group nodes by era tier, then by language family within each tier.

    Args:
        nodes: List of {"id": str, "language": str}.

    Returns:
        {tier_int: {family: [node_id, ...]}}, with family insertion order
        preserved per tier (first-encountered order while scanning `nodes`).
    """
    tiers: dict[int, dict[str, list[str]]] = {}
    for n in nodes:
        tier = get_era_tier(n["language"])
        family = get_lang_family(n["language"])
        if tier not in tiers:
            tiers[tier] = {}
        if family not in tiers[tier]:
            tiers[tier][family] = []
        tiers[tier][family].append(n["id"])
    return tiers


def assign_family_cluster_positions(
    tiered_groups: dict[int, dict[str, list[str]]],
    family_spacing: float = 200,
    node_spacing: float = 40,
) -> dict[str, float]:
    """Compute centered X positions for family clusters within each tier.

    Mirrors JS's Object.values() iteration order: tiers must be visited in
    ascending numeric order (JS objects with integer-like keys always iterate
    that way, unlike Python dicts), while families within a tier iterate in
    insertion order.

    Args:
        tiered_groups: {tier_int: {family: [node_id, ...]}}.
        family_spacing: Horizontal spacing between family cluster centers.
        node_spacing: Horizontal spacing between nodes within a family cluster.

    Returns:
        {node_id: x} flat dict of x-coordinates.
    """
    positions: dict[str, float] = {}
    for tier in sorted(tiered_groups.keys()):
        families = tiered_groups[tier]
        cursor = 0.0
        all_ids_in_tier: list[str] = []
        for ids in families.values():
            family_width = (len(ids) - 1) * node_spacing
            family_start = cursor - family_width / 2
            for i, node_id in enumerate(ids):
                positions[node_id] = family_start + i * node_spacing
            all_ids_in_tier.extend(ids)
            cursor += family_spacing
        xs = [positions[node_id] for node_id in all_ids_in_tier]
        offset = (min(xs) + max(xs)) / 2
        for node_id in all_ids_in_tier:
            positions[node_id] -= offset
    return positions


def build_extra_edges(nodes: list[dict]) -> list[dict]:
    """Build invisible short-spring edges between same-family nodes within the same era tier.

    Args:
        nodes: List of {"id": str, "language": str}.

    Returns:
        List of {"from": str, "to": str, "hidden": True, "physics": True, "length": float}.
    """
    tiered_groups = group_nodes_by_tier_and_family(nodes)
    edges: list[dict] = []
    for tier in sorted(tiered_groups.keys()):
        families = tiered_groups[tier]
        for ids in families.values():
            if len(ids) < 2:
                continue
            tier_factor = tier / 6
            group_factor = min((len(ids) - 1) / 10, 1)
            spring_length = 20 + 100 * (0.5 * tier_factor + 0.5 * group_factor)
            for i in range(len(ids) - 1):
                edges.append(
                    {
                        "from": ids[i],
                        "to": ids[i + 1],
                        "hidden": True,
                        "physics": True,
                        "length": spring_length,
                    }
                )
    return edges
