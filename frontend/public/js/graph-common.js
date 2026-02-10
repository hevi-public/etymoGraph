/**
 * Shared graph constants and utilities used by all renderers (vis.js, G6, etc.)
 * and the concept map. Loaded before renderer-specific files.
 *
 * Contains: language family classification, edge labels, color utilities,
 * uncertainty styling constants, legend rendering, era tier classification,
 * and tree/radial layout computation.
 */

// --- Language family classification ---

// Single source of truth for language family classification: [family, displayName, color, regex]
// Ordered by general frequency in etymology graphs (most common first)
const LANG_FAMILIES = [
    ["germanic",     "Germanic",     "#5B8DEF", /english|german|norse|dutch|frisian|gothic|proto-germanic|proto-west germanic|saxon|scots|yiddish|afrikaans|plautdietsch|limburgish|luxembourgish|cimbrian|alemannic|bavarian|vilamovian|saterland|icelandic|faroese|norwegian|swedish|danish/i],
    ["romance",      "Romance",      "#EF5B5B", /latin|italic|french|spanish|portuguese|romanian|proto-italic|catalan|occitan|sardinian|galician|venetian|sicilian|neapolitan|asturian|aragonese|friulian|ladin|romansch|aromanian|dalmatian/i],
    ["greek",        "Greek",        "#43D9A2", /greek/i],
    ["pie",          "PIE",          "#F5C842", /proto-indo-european/i],
    ["slavic",       "Slavic",       "#CE6BF0", /russian|polish|czech|slovak|serbian|croatian|bulgarian|ukrainian|slovene|proto-slavic|old church slavonic|belarusian|macedonian|sorbian|rusyn|kashubian/i],
    ["celtic",       "Celtic",       "#FF8C42", /irish|welsh|scottish gaelic|breton|cornish|manx|proto-celtic|old irish|gaulish|celtiberian|galatian/i],
    ["indoiranian",  "Indo-Iranian", "#FF6B9D", /sanskrit|hindi|persian|urdu|bengali|punjabi|avestan|pali|proto-indo-iranian|farsi|dari|tajik|pashto|kurdish|balochi|marathi|gujarati|nepali|sinhalese|romani|ossetian|sogdian|bactrian/i],
    ["semitic",      "Semitic",      "#00BCD4", /arabic|hebrew|aramaic|akkadian|proto-semitic|amharic|tigrinya|maltese|phoenician|ugaritic|ge'ez|syriac/i],
    ["uralic",       "Uralic",       "#8BC34A", /finnish|hungarian|estonian|proto-uralic|proto-finnic|sami|karelian|veps|mari|mordvin|udmurt|komi|mansi|khanty|nenets|selkup/i],
    ["baltic",       "Baltic",       "#FFC107", /lithuanian|latvian|proto-baltic|proto-balto-slavic|old prussian|samogitian/i],
    ["turkic",       "Turkic",       "#673AB7", /turkish|ottoman|azerbaijani|kazakh|uzbek|uyghur|turkmen|kyrgyz|tatar|bashkir|chuvash|proto-turkic|gagauz|crimean tatar|yakut/i],
    ["sinotibetan",  "Sino-Tibetan", "#9C27B0", /chinese|mandarin|cantonese|tibetan|burmese|proto-sino-tibetan|middle chinese|old chinese|wu|min|hakka|shanghainese|hokkien/i],
    ["austronesian", "Austronesian", "#2196F3", /indonesian|malay|tagalog|javanese|proto-austronesian|hawaiian|maori|samoan|tongan|fijian|cebuano|ilocano|sundanese|malagasy|chamorro|rapanui/i],
    ["japonic",      "Japonic",      "#E91E63", /japanese|proto-japonic|okinawan|ryukyuan|old japanese/i],
    ["koreanic",     "Koreanic",     "#607D8B", /korean|proto-koreanic|middle korean|old korean|jeju/i],
    ["bantu",        "Bantu",        "#795548", /swahili|zulu|xhosa|yoruba|igbo|proto-bantu|lingala|shona|kikuyu|luganda|kinyarwanda|setswana|sesotho|chichewa/i],
    ["dravidian",    "Dravidian",    "#009688", /tamil|telugu|malayalam|kannada|proto-dravidian|brahui|tulu|gondi/i],
    ["kartvelian",   "Kartvelian",   "#4CAF50", /georgian|mingrelian|svan|laz|proto-kartvelian|old georgian/i],
    ["armenian",     "Armenian",     "#FF5722", /armenian|proto-armenian|classical armenian|old armenian/i],
    ["albanian",     "Albanian",     "#CDDC39", /albanian|proto-albanian|gheg|tosk/i],
];

const DEFAULT_FAMILY_COLOR = "#A0A0B8";

function classifyLang(lang) {
    for (const [family, , color, regex] of LANG_FAMILIES) {
        if (regex.test(lang)) return { family, color };
    }
    return { family: "other", color: DEFAULT_FAMILY_COLOR };
}

// eslint-disable-next-line no-unused-vars
function langColor(lang) {
    return classifyLang(lang).color;
}

function getLangFamily(lang) {
    return classifyLang(lang).family;
}

// --- Edge labels ---

const EDGE_LABELS = {
    inh: "inherited", bor: "borrowed", der: "derived", cog: "cognate",
    component: "component", mention: "related",
};

// --- Color utilities ---

const UNCERTAINTY_DESATURATION = 0.6;  // Multiply saturation by this factor

function desaturateColor(hex, factor) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const gray = (r + g + b) / 3;
    const nr = Math.round(r + (gray - r) * (1 - factor));
    const ng = Math.round(g + (gray - g) * (1 - factor));
    const nb = Math.round(b + (gray - b) * (1 - factor));
    return `#${nr.toString(16).padStart(2, "0")}${ng.toString(16).padStart(2, "0")}${nb.toString(16).padStart(2, "0")}`;
}

const OPACITY_BY_HOP = [1.0, 0.9, 0.5, 0.1]; // 0 hops, 1 hop, 2 hops, 3+ hops

function colorWithOpacity(color, opacity) {
    const rgbaMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (rgbaMatch) return `rgba(${rgbaMatch[1]},${rgbaMatch[2]},${rgbaMatch[3]},${opacity})`;
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${opacity})`;
}

function extractOpacity(colorStr) {
    const m = colorStr.match(/,\s*([\d.]+)\)$/);
    return m ? parseFloat(m[1]) : 1.0;
}

function opacityForHops(hops) {
    if (hops >= OPACITY_BY_HOP.length) return OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1];
    return OPACITY_BY_HOP[hops];
}

// --- Legend rendering ---

function renderLegend() {
    const container = document.getElementById("legend-container");
    if (!container) return;

    container.innerHTML = "";

    for (const [family, displayName] of LANG_FAMILIES) {
        const item = document.createElement("span");
        item.className = "legend-item";
        item.innerHTML = `<span class="dot ${family}"></span>${displayName}`;
        container.appendChild(item);
    }

    const otherItem = document.createElement("span");
    otherItem.className = "legend-item";
    otherItem.innerHTML = "<span class=\"dot other\"></span>Other";
    container.appendChild(otherItem);
}

document.addEventListener("DOMContentLoaded", renderLegend);

// --- Graph data utilities ---

function findRootAndWordNodes(nodes) {
    const wordNode = nodes.find((n) => n.level === 0);
    const etymRoot = nodes.reduce((min, n) => (n.level < min.level ? n : min), nodes[0]);
    return {
        rootNodeId: etymRoot ? etymRoot.id : null,
        wordNodeId: wordNode ? wordNode.id : null,
    };
}

// --- Era tier classification ---

const ERA_TIERS = [
    { name: "Deep Proto", date: "~4000+ BCE", y: 800 },
    { name: "Branch Proto", date: "~2000–500 BCE", y: 650 },
    { name: "Classical/Ancient", date: "~500 BCE–500 CE", y: 500 },
    { name: "Early Medieval", date: "~500–1000 CE", y: 350 },
    { name: "Late Medieval", date: "~1000–1500 CE", y: 200 },
    { name: "Early Modern", date: "~1500–1700 CE", y: 50 },
    { name: "Modern", date: "~1700–present", y: -100 },
    { name: "Contemporary", date: "recent", y: -250 },
];

const DEEP_PROTO = /^Proto-(Indo-European|Uralic|Afro-Asiatic|Sino-Tibetan|Austronesian|Niger-Congo|Trans-New Guinea|Dravidian|Turkic|Mongolic|Japonic|Koreanic|Tai|Austroasiatic|Nilo-Saharan)$/i;
const CLASSICAL_SPECIFIC = /^(Latin|Sanskrit|Avestan|Gothic|Akkadian|Sumerian|Tocharian [AB]|Pali|Oscan|Umbrian|Mycenaean Greek|Hittite|Luwian|Lydian|Lycian|Sogdian|Bactrian|Prakrit|Elamite)$/i;

function getEraTier(lang) {
    if (!lang) return 6;
    if (DEEP_PROTO.test(lang)) return 0;
    if (/^Proto-/.test(lang)) return 1;
    if (/^(Ancient |Classical |Biblical )/.test(lang)) return 2;
    if (CLASSICAL_SPECIFIC.test(lang)) return 2;
    if (/^Old /.test(lang)) return 3;
    if (/^Middle |^Anglo-Norman$/i.test(lang)) return 4;
    if (/^Early Modern /.test(lang)) return 5;
    return 6;
}

/** Group nodes by era tier, then by language family within each tier.
 *  Returns { tier: { family: [nodeId, ...] } } */
function groupNodesByTierAndFamily(nodes) {
    const tiers = {};
    for (const n of nodes) {
        const tier = getEraTier(n.language);
        const family = getLangFamily(n.language);
        if (!tiers[tier]) tiers[tier] = {};
        if (!tiers[tier][family]) tiers[tier][family] = [];
        tiers[tier][family].push(n.id);
    }
    return tiers;
}

/** Compute centered X positions for family clusters within each tier. Returns { nodeId: x } */
function assignFamilyClusterPositions(tieredGroups, { familySpacing = 200, nodeSpacing = 40 } = {}) {
    const positions = {};
    for (const families of Object.values(tieredGroups)) {
        let cursor = 0;
        const allIdsInTier = [];
        for (const ids of Object.values(families)) {
            const familyWidth = (ids.length - 1) * nodeSpacing;
            const familyStart = cursor - familyWidth / 2;
            ids.forEach((id, i) => {
                positions[id] = familyStart + i * nodeSpacing;
            });
            allIdsInTier.push(...ids);
            cursor += familySpacing;
        }
        // Center all positions in this tier around x=0
        const xs = allIdsInTier.map((id) => positions[id]);
        const offset = (Math.min(...xs) + Math.max(...xs)) / 2;
        for (const id of allIdsInTier) {
            positions[id] -= offset;
        }
    }
    return positions;
}

// --- Tree layout computation ---

const TREE_LEVEL_SPACING = 110;
const TREE_SIBLING_SPACING = 90;

/**
 * Compute linear tree positions: siblings fan out horizontally under their parent.
 * Used for concept maps (no level data) where a top-down tree shape is appropriate.
 */
function computeLinearTreePositions(children, nodeMap, bfsDepth, rootId) {
    const subtreeWidth = {};
    function computeWidth(id) {
        const kids = children[id] || [];
        if (kids.length === 0) {
            subtreeWidth[id] = TREE_SIBLING_SPACING;
            return subtreeWidth[id];
        }
        let total = 0;
        for (const kid of kids) total += computeWidth(kid);
        subtreeWidth[id] = total;
        return total;
    }
    computeWidth(rootId);

    const positions = {};
    function assignPositions(id, xCenter) {
        const node = nodeMap[id];
        const level = node?.level ?? bfsDepth[id] ?? 0;
        positions[id] = { x: xCenter, y: level * TREE_LEVEL_SPACING };

        const kids = children[id] || [];
        if (kids.length === 0) return;

        const totalWidth = subtreeWidth[id];
        let xStart = xCenter - totalWidth / 2;
        for (const kid of kids) {
            const kidWidth = subtreeWidth[kid];
            assignPositions(kid, xStart + kidWidth / 2);
            xStart += kidWidth;
        }
    }
    assignPositions(rootId, 0);
    return positions;
}

const RADIAL_MIN_ANGLE = 0.1;  // Minimum angular span per leaf (radians)
const RADIAL_RING_SPACING = 110;  // Pixels between concentric rings

/**
 * Compute radial tree positions: nodes fan in concentric rings from root.
 * Matches the radial shape that forceAtlas2Based converges to, so physics
 * only fine-tunes rather than rearranges.
 */
function computeRadialPositions(children, nodeMap, bfsDepth, rootId) {
    const angularSpan = {};
    function computeSpan(id) {
        const kids = children[id] || [];
        if (kids.length === 0) {
            angularSpan[id] = RADIAL_MIN_ANGLE;
            return RADIAL_MIN_ANGLE;
        }
        let total = 0;
        for (const kid of kids) total += computeSpan(kid);
        angularSpan[id] = total;
        return total;
    }
    computeSpan(rootId);

    const positions = {};
    positions[rootId] = { x: 0, y: 0 };

    function assignRadial(id, angleStart, angleEnd) {
        const kids = children[id] || [];
        if (kids.length === 0) return;

        const parentSpan = angularSpan[id];
        let cursor = angleStart;

        for (const kid of kids) {
            const kidFraction = angularSpan[kid] / parentSpan;
            const kidAngleStart = cursor;
            const kidAngleEnd = cursor + (angleEnd - angleStart) * kidFraction;
            const kidAngle = (kidAngleStart + kidAngleEnd) / 2;

            const depth = bfsDepth[kid] || 1;
            const radius = depth * RADIAL_RING_SPACING;
            positions[kid] = {
                x: radius * Math.cos(kidAngle),
                y: radius * Math.sin(kidAngle),
            };

            assignRadial(kid, kidAngleStart, kidAngleEnd);
            cursor = kidAngleEnd;
        }
    }
    assignRadial(rootId, 0, 2 * Math.PI);
    return positions;
}

/**
 * Shift non-fixed nodes toward the barycenter of their neighbors across ALL edges.
 * Accounts for cognates, borrowings, and mentions that the tree layout ignores.
 */
function applyBarycentricRefinement(positions, nodes, edges, rootId, iterations = 3) {
    const adj = {};
    for (const n of nodes) adj[n.id] = [];
    for (const e of edges) {
        if (adj[e.from]) adj[e.from].push(e.to);
        if (adj[e.to]) adj[e.to].push(e.from);
    }

    const damping = 0.5;

    for (let iter = 0; iter < iterations; iter++) {
        for (const n of nodes) {
            if (n.id === rootId) continue;
            const neighbors = adj[n.id] || [];
            if (neighbors.length === 0) continue;

            let sumX = 0, sumY = 0, count = 0;
            for (const nid of neighbors) {
                const pos = positions[nid];
                if (pos) { sumX += pos.x; sumY += pos.y; count++; }
            }
            if (count === 0) continue;

            const cur = positions[n.id];
            if (!cur) continue;
            cur.x += (sumX / count - cur.x) * damping;
            cur.y += (sumY / count - cur.y) * damping;
        }
    }
}

/**
 * Compute tree-based initial positions for force-directed layout.
 * BFS from root discovers parent-child relationships. Then:
 * - Etymology graphs (nodes have levels) -> radial ring layout
 * - Concept maps (no levels) -> linear top-down tree layout
 * Both get barycentric refinement to account for non-tree edges.
 */
function computeTreePositions(nodes, edges, rootId) {
    if (!nodes.length || !rootId) return {};
    if (!edges.length) return { [rootId]: { x: 0, y: 0 } };

    const nodeMap = {};
    for (const n of nodes) nodeMap[n.id] = n;

    const adj = {};
    for (const n of nodes) adj[n.id] = [];
    for (const e of edges) {
        if (adj[e.from]) adj[e.from].push(e.to);
        if (adj[e.to]) adj[e.to].push(e.from);
    }

    const children = {};
    const bfsDepth = {};
    const visited = new Set();
    const queue = [rootId];
    visited.add(rootId);
    bfsDepth[rootId] = 0;

    while (queue.length > 0) {
        const cur = queue.shift();
        if (!children[cur]) children[cur] = [];
        for (const neighbor of (adj[cur] || [])) {
            if (visited.has(neighbor)) continue;
            visited.add(neighbor);
            bfsDepth[neighbor] = bfsDepth[cur] + 1;
            children[cur].push(neighbor);
            queue.push(neighbor);
        }
    }

    const hasLevels = nodes.some(n => n.level != null);

    let positions;
    if (hasLevels) {
        positions = computeRadialPositions(children, nodeMap, bfsDepth, rootId);
    } else {
        positions = computeLinearTreePositions(children, nodeMap, bfsDepth, rootId);
    }

    // Place disconnected nodes in a fan beyond the positioned nodes
    const unvisited = nodes.filter(n => !visited.has(n.id));
    if (unvisited.length > 0) {
        const allPos = Object.values(positions);
        const maxR = allPos.length > 0
            ? Math.max(...allPos.map(p => Math.sqrt(p.x * p.x + p.y * p.y)))
            : 0;
        const fanRadius = maxR + TREE_SIBLING_SPACING * 2;
        const angleStep = (2 * Math.PI) / Math.max(unvisited.length, 1);
        unvisited.forEach((n, i) => {
            const angle = i * angleStep;
            positions[n.id] = {
                x: fanRadius * Math.cos(angle),
                y: fanRadius * Math.sin(angle),
            };
        });
    }

    applyBarycentricRefinement(positions, nodes, edges, rootId);

    return positions;
}

// Expose for unit testing
if (typeof window !== "undefined") {
    window.classifyLang = classifyLang;
    window.findRootAndWordNodes = findRootAndWordNodes;
}
