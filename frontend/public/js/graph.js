const graphContainer = document.getElementById("graph");

// --- Pure utility functions extracted from formatEtymologyText ---

function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Build lookup from templates: word → {word, lang_code} for linkable terms.
// Kaikki templates have args as dict with string keys: "1"=source_lang, "2"=target_lang, "3"=word
// For cognates: "1"=lang_code, "2"=word
function buildTemplateLookup(templates) {
    const lookup = {};
    if (!templates || !templates.length) return lookup;
    // Process cognates first, then ancestry types so ancestry takes priority for shared words
    for (const t of templates) {
        if (!t.args || t.name !== "cog") continue;
        const langCode = t.args["1"] || "";
        const w = t.args["2"] || "";
        if (w && langCode) lookup[w] = { word: w, lang_code: langCode };
    }
    for (const t of templates) {
        if (!t.args) continue;
        if (!["inh", "bor", "der"].includes(t.name)) continue;
        const langCode = t.args["2"] || "";
        const w = t.args["3"] || "";
        if (w && langCode) lookup[w] = { word: w, lang_code: langCode };
    }
    return lookup;
}

function makeEtymLink(displayText, word, templateLookup) {
    const entry = templateLookup[word] || templateLookup[word.replace(/^\*/, "")];
    if (!entry) return escapeHtml(displayText);
    return `<a class="etym-link" href="#" data-word="${escapeHtml(entry.word)}" data-lang-code="${escapeHtml(entry.lang_code)}">${escapeHtml(displayText)}</a>`;
}

function linkifyEtymologyText(escaped, templateLookup) {
    if (!Object.keys(templateLookup).length) return escaped;
    // Sort by length descending to match longer words first
    const words = Object.keys(templateLookup).sort((a, b) => b.length - a.length);
    const pattern = new RegExp("(?<![\\w*])(" + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join("|") + ")(?!\\w)", "g");
    return escaped.replace(pattern, (match) => {
        const entry = templateLookup[match];
        if (!entry) return match;
        return `<a class="etym-link" href="#" data-word="${escapeHtml(entry.word)}" data-lang-code="${escapeHtml(entry.lang_code)}">${match}</a>`;
    });
}

function splitEtymologySections(text) {
    let tree = "";
    let prose = "";
    let cognates = "";

    const lines = text.split("\n");
    let section = "auto"; // auto-detect

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed === "Etymology tree") {
            section = "tree";
            continue;
        }
        if (trimmed === "Cognates" || trimmed === "Cognates:") {
            section = "cognates";
            continue;
        }
        if (section === "tree" && /^(From |Borrowed |Learned |Coined |Back-formation|A |The |Inherited |Uncertain|Originally|Perhaps|Probably|Possibly|Compare |Cf\.|Related |See |Also |Equivalent |Compound |Blend |Variant |Alteration |Clipping |Abbreviation |Acronym |Named )/.test(trimmed)) {
            section = "prose";
        }

        if (section === "tree") {
            tree += (tree ? "\n" : "") + trimmed;
        } else if (section === "cognates") {
            cognates += (cognates ? "\n" : "") + trimmed;
        } else {
            prose += (prose ? "\n" : "") + trimmed;
            section = "prose";
        }
    }

    return { tree, prose, cognates };
}

// Render etymology tree as a chain with arrows.
// Chain items are "Language word" (e.g. "Old English wæter") or "word (Language)".
function renderEtymologyChain(treeText, templateLookup) {
    const steps = treeText.split("\n").map(s => {
        const parenMatch = s.match(/^(\*?\S+)\s*\((.+)\)$/);
        if (parenMatch) {
            return makeEtymLink(parenMatch[1], parenMatch[1], templateLookup) + " (" + escapeHtml(parenMatch[2]) + ")";
        }
        const lastSpace = s.lastIndexOf(" ");
        if (lastSpace > 0) {
            const word = s.slice(lastSpace + 1);
            const lang = s.slice(0, lastSpace);
            const entry = templateLookup[word] || templateLookup[word.replace(/^\*/, "")];
            if (entry) {
                return escapeHtml(lang) + " " + makeEtymLink(word, word, templateLookup);
            }
        }
        return escapeHtml(s);
    });
    return '<div class="etym-chain">' + steps.join(' <span class="etym-arrow">→</span> ') + "</div>";
}

// Render cognates as a compact collapsible list.
// Cognates are "Language word ("gloss")" e.g. 'Scots watter ("water")'.
function renderEtymologyCognates(cognatesText, templateLookup) {
    const items = cognatesText.split("\n").map((c) => c.replace(/^\*\s*/, "").trim()).filter(Boolean);
    let html = '<details class="etym-cognates"><summary>Cognates (' + items.length + ")</summary><p>";
    html += items.map(c => {
        const glossMatch = c.match(/^(.+?)\s+(\(".+"\))$/);
        if (glossMatch) {
            const before = glossMatch[1];
            const gloss = glossMatch[2];
            const ls = before.lastIndexOf(" ");
            if (ls > 0) {
                const word = before.slice(ls + 1);
                const lang = before.slice(0, ls);
                return escapeHtml(lang) + " " + makeEtymLink(word, word, templateLookup) + " " + '<span class="etym-gloss">' + escapeHtml(gloss) + "</span>";
            }
            return makeEtymLink(before, before, templateLookup) + " " + '<span class="etym-gloss">' + escapeHtml(gloss) + "</span>";
        }
        return linkifyEtymologyText(escapeHtml(c), templateLookup);
    }).join(", ");
    html += "</p></details>";
    return html;
}

function buildWiktionaryUrl(word, lang) {
    if (lang.startsWith("Proto-")) {
        const cleanWord = word.replace(/^\*/, "");
        return `https://en.wiktionary.org/wiki/Reconstruction:${encodeURIComponent(lang)}/${encodeURIComponent(cleanWord)}`;
    }
    return `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}#${encodeURIComponent(lang)}`;
}

// --- formatEtymologyText orchestrator ---

function formatEtymologyText(text, templates) {
    if (!text) return '<span class="etym-empty">No etymology text available.</span>';

    const templateLookup = buildTemplateLookup(templates);
    const { tree, prose, cognates } = splitEtymologySections(text);

    let html = "";

    if (tree) {
        html += renderEtymologyChain(tree, templateLookup);
    }

    // Render prose inline (straightforward ~10 lines)
    if (prose) {
        let escaped = escapeHtml(prose);
        escaped = escaped.replace(/\b(from|From|of)\s+((?:Proto-|Middle |Old |Late |Ancient |Medieval |Vulgar |Biblical |Classical )*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
            '$1 <strong>$2</strong>');
        escaped = escaped.replace(/\(("[^"]*")\)/g, '<span class="etym-gloss">($1)</span>');
        escaped = linkifyEtymologyText(escaped, templateLookup);
        html += '<p class="etym-prose">' + escaped + "</p>";
    }

    if (cognates) {
        html += renderEtymologyCognates(cognates, templateLookup);
    }

    return html || '<span class="etym-empty">No etymology text available.</span>';
}

// --- Graph constants and utilities ---

// Single source of truth for language family classification: [family, color, regex]
const LANG_FAMILIES = [
    ["germanic",    "#5B8DEF", /english|german|norse|dutch|frisian|gothic|proto-germanic|proto-west germanic|saxon|scots|yiddish|afrikaans|plautdietsch|limburgish|luxembourgish|cimbrian|alemannic|bavarian|vilamovian|saterland/i],
    ["romance",     "#EF5B5B", /latin|italic|french|spanish|portuguese|romanian|proto-italic|catalan|occitan|sardinian|galician|venetian|sicilian|neapolitan|asturian/i],
    ["greek",       "#43D9A2", /greek/i],
    ["pie",         "#F5C842", /proto-indo-european/i],
    ["slavic",      "#CE6BF0", /russian|polish|czech|slovak|serbian|croatian|bulgarian|ukrainian|slovene|proto-slavic|old church slavonic|belarusian|macedonian|sorbian/i],
    ["celtic",      "#FF8C42", /irish|welsh|scottish gaelic|breton|cornish|manx|proto-celtic|old irish/i],
    ["indoiranian", "#FF6B9D", /sanskrit|hindi|persian|urdu|bengali|punjabi|avestan|pali|proto-indo-iranian/i],
    ["semitic",     "#00BCD4", /arabic|hebrew|aramaic|akkadian|proto-semitic/i],
    ["uralic",      "#8BC34A", /finnish|hungarian|estonian|proto-uralic|proto-finnic/i],
];

const DEFAULT_FAMILY_COLOR = "#A0A0B8";

// Derive LANG_COLORS for use in legend CSS class mapping
const LANG_COLORS = Object.fromEntries([
    ...LANG_FAMILIES.map(([family, color]) => [family, color]),
    ["other", DEFAULT_FAMILY_COLOR],
]);

function classifyLang(lang) {
    for (const [family, color, regex] of LANG_FAMILIES) {
        if (regex.test(lang)) return { family, color };
    }
    return { family: "other", color: DEFAULT_FAMILY_COLOR };
}

function langColor(lang) {
    return classifyLang(lang).color;
}

function getLangFamily(lang) {
    return classifyLang(lang).family;
}

const EDGE_LABELS = {
    inh: "inherited", bor: "borrowed", der: "derived", cog: "cognate",
    component: "component", mention: "related",
};

// --- Uncertainty styling constants ---

const UNCERTAINTY_BORDER_DASHES = [5, 5];
const UNCERTAINTY_DESATURATION = 0.6;  // Multiply saturation by this factor

// Desaturate a hex color for uncertain nodes
function desaturateColor(hex, factor) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    // Simple desaturation: move toward gray
    const gray = (r + g + b) / 3;
    const nr = Math.round(r + (gray - r) * (1 - factor));
    const ng = Math.round(g + (gray - g) * (1 - factor));
    const nb = Math.round(b + (gray - b) * (1 - factor));
    return `#${nr.toString(16).padStart(2, "0")}${ng.toString(16).padStart(2, "0")}${nb.toString(16).padStart(2, "0")}`;
}

// Build vis.js node style object for uncertainty
function uncertaintyNodeStyle(baseColor, uncertainty) {
    if (!uncertainty || !uncertainty.is_uncertain) {
        return { color: baseColor };
    }
    const desaturated = desaturateColor(baseColor, UNCERTAINTY_DESATURATION);
    return {
        color: {
            background: desaturated,
            border: desaturated,
            highlight: { background: desaturated, border: "#fff" },
        },
        borderWidth: 2,
        borderDashes: UNCERTAINTY_BORDER_DASHES,
        shapeProperties: { borderDashes: UNCERTAINTY_BORDER_DASHES },
    };
}

const OPACITY_BY_HOP = [1.0, 0.9, 0.5, 0.1]; // 0 hops, 1 hop, 2 hops, 3+ hops

function colorWithOpacity(hex, opacity) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${opacity})`;
}

function opacityForHops(hops) {
    if (hops >= OPACITY_BY_HOP.length) return OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1];
    return OPACITY_BY_HOP[hops];
}

// --- Layout Strategy Engine ---

// Era tier definitions (used by eraLayered strategy)
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

// Shared vis.js options; each layout overrides only what differs
function baseGraphOptions(overrides) {
    const base = {
        layout: { improvedLayout: true },
        edges: {
            color: { color: "#555", highlight: "#aaa" },
            font: { color: "#999", size: 11, strokeWidth: 0 },
            smooth: { type: "continuous" },
            length: 200,
        },
        nodes: {
            shape: "box",
            borderWidth: 0,
            font: { size: 13, multi: true, color: "#fff" },
            margin: 10,
        },
        physics: {
            solver: "forceAtlas2Based",
            forceAtlas2Based: {},
            stabilization: false,
        },
        interaction: {
            zoomView: false,
            dragView: true,
            hover: true,
        },
    };
    // Deep-merge overrides into base
    for (const [section, values] of Object.entries(overrides)) {
        if (typeof values === "object" && !Array.isArray(values) && base[section]) {
            base[section] = { ...base[section], ...values };
            // One more level for nested objects like forceAtlas2Based
            for (const [k, v] of Object.entries(values)) {
                if (typeof v === "object" && !Array.isArray(v) && base[section][k] && typeof base[section][k] === "object") {
                    base[section][k] = { ...base[section][k], ...v };
                }
            }
        } else {
            base[section] = values;
        }
    }
    return base;
}

const LAYOUTS = {
    "force-directed": {
        name: "force-directed",
        label: "Force-Directed",
        getGraphOptions() {
            return baseGraphOptions({
                physics: {
                    forceAtlas2Based: {
                        gravitationalConstant: -120,
                        centralGravity: 0.01,
                        springLength: 200,
                        springConstant: 0.05,
                        damping: 0.7,
                    },
                },
            });
        },
        buildVisNodes(nodes, rootId) {
            const baseColors = {};
            const visNodes = nodes.map((n) => {
                const isRoot = n.id === rootId;
                const color = langColor(n.language);
                baseColors[n.id] = color;
                const style = uncertaintyNodeStyle(color, n.uncertainty);
                return {
                    ...n,
                    label: `${n.label}\n(${n.language})`,
                    ...style,
                    mass: isRoot ? 5 : Math.max(1, 5 / Math.pow(2, Math.abs(n.level))),
                    ...(isRoot ? { x: 0, y: 0, fixed: { x: true, y: true } } : {}),
                };
            });
            return { visNodes, nodeBaseColors: baseColors };
        },
        buildExtraEdges() {
            return [];
        },
        getInitialView() {
            return { position: { x: 0, y: 0 }, scale: 1 };
        },
        onBeforeDrawing: null,
    },

    "era-layered": {
        name: "era-layered",
        label: "Era Layers",
        getGraphOptions() {
            return baseGraphOptions({
                edges: { length: 150 },
                physics: {
                    forceAtlas2Based: {
                        gravitationalConstant: -80,
                        centralGravity: 0.001,
                        springLength: 500,
                        springConstant: 0.002,
                        damping: 0.95,
                        avoidOverlap: 0.7,
                    },
                },
            });
        },
        buildVisNodes(nodes) {
            const baseColors = {};
            const tierFamilyGroups = groupNodesByTierAndFamily(nodes);
            const nodeXPositions = assignFamilyClusterPositions(tierFamilyGroups);
            const visNodes = nodes.map((n) => {
                const color = langColor(n.language);
                baseColors[n.id] = color;
                const tier = getEraTier(n.language);
                const yPos = ERA_TIERS[tier].y;
                const style = uncertaintyNodeStyle(color, n.uncertainty);
                return {
                    ...n,
                    label: `${n.label}\n(${n.language})`,
                    ...style,
                    mass: 1,
                    x: nodeXPositions[n.id] || 0,
                    y: yPos,
                    fixed: { y: true },
                };
            });
            return { visNodes, nodeBaseColors: baseColors };
        },
        buildExtraEdges(nodes) {
            // Build invisible short-spring edges between same-family nodes within the same era tier
            const tieredGroups = groupNodesByTierAndFamily(nodes);
            const edges = [];
            for (const [tier, families] of Object.entries(tieredGroups)) {
                for (const ids of Object.values(families)) {
                    if (ids.length < 2) continue;
                    const tierFactor = parseInt(tier) / 6;
                    const groupFactor = Math.min((ids.length - 1) / 10, 1);
                    const springLength = 20 + 100 * (0.5 * tierFactor + 0.5 * groupFactor);
                    for (let i = 0; i < ids.length - 1; i++) {
                        edges.push({
                            from: ids[i],
                            to: ids[i + 1],
                            hidden: true,
                            physics: true,
                            length: springLength,
                        });
                    }
                }
            }
            return edges;
        },
        getInitialView(nodes, wordNodeId) {
            const wordNode = nodes.find(n => n.id === wordNodeId);
            const wordTier = wordNode ? getEraTier(wordNode.language) : 6;
            const startY = ERA_TIERS[wordTier]?.y || 0;
            return { position: { x: 0, y: startY }, scale: 0.8 };
        },
        onBeforeDrawing(network, ctx) {
            const bandHeight = 150;
            const halfBand = bandHeight / 2;
            // Wide enough to always cover the viewport even when panned far horizontally
            const bandWidth = 20000;
            const labelX = -bandWidth / 2 + 20;

            for (let i = 0; i < ERA_TIERS.length; i++) {
                const tier = ERA_TIERS[i];
                const top = tier.y - halfBand;

                if (i % 2 === 0) {
                    ctx.fillStyle = "rgba(255,255,255,0.03)";
                    ctx.fillRect(-bandWidth / 2, top, bandWidth, bandHeight);
                }

                ctx.fillStyle = "rgba(255,255,255,0.25)";
                ctx.font = "bold 14px sans-serif";
                ctx.textAlign = "left";
                ctx.textBaseline = "middle";
                ctx.fillText(tier.name, labelX, tier.y - 8);
                ctx.font = "11px sans-serif";
                ctx.fillStyle = "rgba(255,255,255,0.15)";
                ctx.fillText(tier.date, labelX, tier.y + 10);
            }
        },
    },
};

let currentLayout = localStorage.getItem("graphLayout") || "era-layered";
// Validate stored layout
if (!LAYOUTS[currentLayout]) currentLayout = "era-layered";

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let currentNodes = [];
let nodeBaseColors = {};  // id → hex color
let rootNodeId = null;   // etymological root (deepest ancestor)
let wordNodeId = null;   // searched word

// --- updateGraph helpers ---

function findRootAndWordNodes(nodes) {
    const wordNode = nodes.find((n) => n.level === 0);
    const etymRoot = nodes.reduce((min, n) => (n.level < min.level ? n : min), nodes[0]);
    return {
        rootNodeId: etymRoot ? etymRoot.id : null,
        wordNodeId: wordNode ? wordNode.id : null,
    };
}

function buildVisEdges(edges) {
    return edges.map((e) => {
        const isMention = e.label === "component" || e.label === "mention";
        return {
            ...e,
            rawType: e.label,
            label: EDGE_LABELS[e.label] || e.label,
            arrows: "to",
            dashes: e.label === "bor" || e.label === "cog" || isMention,
            color: e.label === "cog" ? { color: "#F5C842", highlight: "#FFE066" }
                 : isMention ? { color: "#888", highlight: "#aaa" }
                 : undefined,
        };
    });
}

function updateGraph(data) {
    if (network) {
        network.destroy();
    }
    currentNodes = data.nodes;

    const found = findRootAndWordNodes(data.nodes);
    rootNodeId = found.rootNodeId;
    wordNodeId = found.wordNodeId;

    const layout = LAYOUTS[currentLayout];
    const options = layout.getGraphOptions();
    const { visNodes, nodeBaseColors: colors } = layout.buildVisNodes(data.nodes, rootNodeId);
    nodeBaseColors = colors;

    nodesDataSet = new vis.DataSet(visNodes);
    const nodes = nodesDataSet;
    const extraEdges = layout.buildExtraEdges(data.nodes);
    edgesDataSet = new vis.DataSet([...buildVisEdges(data.edges), ...extraEdges]);
    const edges = edgesDataSet;
    network = new vis.Network(graphContainer, { nodes, edges }, options);

    if (layout.onBeforeDrawing) {
        network.on("beforeDrawing", (ctx) => layout.onBeforeDrawing(network, ctx));
    }

    const view = layout.getInitialView(data.nodes, wordNodeId, rootNodeId);
    network.moveTo({ ...view, animation: false });

    network.on("click", (params) => {
        if (params.nodes.length > 0) {
            const clickedId = params.nodes[0];
            const node = currentNodes.find((n) => n.id === clickedId);
            if (node) {
                showDetail(node.label, node.language);
            }
            applyBrightnessFromNode(clickedId, edges);
            const pos = network.getPositions([clickedId])[clickedId];
            if (pos) {
                network.moveTo({
                    position: { x: pos.x, y: pos.y },
                    animation: { duration: 400, easingFunction: "easeInOutQuad" },
                });
            }
        } else {
            // Clicked on empty space — reset all nodes to full brightness
            resetBrightness();
        }
    });
}

// Trackpad: pinch zooms (ctrlKey), two-finger scroll pans
// Added once outside updateGraph to prevent listener accumulation
graphContainer.addEventListener("wheel", (e) => {
    if (!network) return;
    e.preventDefault();
    if (e.ctrlKey) {
        const scale = network.getScale();
        const newScale = scale * (1 - e.deltaY * 0.01);
        network.moveTo({ scale: Math.max(0.1, Math.min(5, newScale)), animation: false });
    } else {
        const pos = network.getViewPosition();
        const scale = network.getScale();
        network.moveTo({
            position: { x: pos.x + e.deltaX / scale, y: pos.y + e.deltaY / scale },
            animation: false,
        });
    }
}, { passive: false });

function selectNodeById(nodeId) {
    if (!network) return;
    network.selectNodes([nodeId]);
    const pos = network.getPositions([nodeId])[nodeId];
    if (pos) {
        network.moveTo({
            position: { x: pos.x, y: pos.y },
            animation: { duration: 400, easingFunction: "easeInOutQuad" },
        });
    }
    applyBrightnessFromNode(nodeId, edgesDataSet);
    const node = currentNodes.find((n) => n.id === nodeId);
    if (node) showDetail(node.label, node.language);
}

// --- buildConnectionsPanel helper ---

function groupEdgesByType(edgesDS, nodeId) {
    const grouped = {};
    edgesDS.forEach((e) => {
        const rawType = e.rawType || e.label;
        let targetId = null;
        if (e.from === nodeId) targetId = e.to;
        else if (e.to === nodeId) targetId = e.from;
        if (!targetId) return;

        if (!grouped[rawType]) grouped[rawType] = [];
        grouped[rawType].push(targetId);
    });
    return grouped;
}

function buildConnectionsPanel(nodeId) {
    const container = document.getElementById("detail-connections");
    container.innerHTML = "";

    if (!edgesDataSet) return;

    const CONNECTION_SECTIONS = {
        inh: "Inherited",
        bor: "Borrowed",
        der: "Derived",
        cog: "Cognate",
        component: "Component",
        mention: "Related",
    };

    const grouped = groupEdgesByType(edgesDataSet, nodeId);

    for (const [type, label] of Object.entries(CONNECTION_SECTIONS)) {
        const targets = grouped[type];
        if (!targets || targets.length === 0) continue;

        const h3 = document.createElement("h3");
        h3.textContent = label;
        container.appendChild(h3);

        const ul = document.createElement("ul");
        ul.className = "connection-list";
        for (const tid of targets) {
            const node = currentNodes.find((n) => n.id === tid);
            if (!node) continue;
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.href = "#";
            a.textContent = `${node.label} (${node.language})`;
            a.addEventListener("click", (ev) => {
                ev.preventDefault();
                selectNodeById(tid);
            });
            li.appendChild(a);
            ul.appendChild(li);
        }
        container.appendChild(ul);
    }
}

// --- showDetail ---

function renderUncertaintyBadge(uncertainty) {
    const badge = document.getElementById("detail-uncertainty");
    if (!uncertainty || !uncertainty.is_uncertain) {
        badge.hidden = true;
        badge.className = "uncertainty-badge";
        badge.innerHTML = "";
        return;
    }

    const typeLabels = {
        unknown: "Unknown origin",
        uncertain: "Uncertain origin",
        disputed: "Disputed etymology",
    };

    badge.hidden = false;
    badge.className = `uncertainty-badge ${uncertainty.type || "uncertain"}`;
    badge.innerHTML = `
        <span>${typeLabels[uncertainty.type] || "Uncertain"}</span>
        <span class="confidence">(${uncertainty.confidence} confidence)</span>
    `;
}

async function showDetail(word, lang) {
    const panel = document.getElementById("detail-panel");
    const wordEl = document.getElementById("detail-word");
    const langEl = document.getElementById("detail-lang");
    const posEl = document.getElementById("detail-pos");
    const ipaEl = document.getElementById("detail-ipa");
    const defsEl = document.getElementById("detail-defs");
    const etymEl = document.getElementById("detail-etym");

    wordEl.textContent = word;
    const wiktLink = document.getElementById("detail-wikt");
    wiktLink.href = buildWiktionaryUrl(word, lang);
    langEl.textContent = lang;
    posEl.textContent = "";
    ipaEl.textContent = "";
    defsEl.innerHTML = "";
    etymEl.textContent = "";
    renderUncertaintyBadge(null);  // Clear until loaded
    panel.hidden = false;

    // Build connections from graph edges
    const nodeId = `${word}:${lang}`;
    buildConnectionsPanel(nodeId);

    try {
        const data = await getWord(word, lang);
        posEl.textContent = data.pos || "";
        ipaEl.textContent = data.pronunciation || "";
        renderUncertaintyBadge(data.etymology_uncertainty);
        defsEl.innerHTML = "";
        (data.definitions || []).forEach((d) => {
            const li = document.createElement("li");
            li.textContent = d;
            defsEl.appendChild(li);
        });
        etymEl.innerHTML = formatEtymologyText(data.etymology_text, data.etymology_templates);
    } catch (e) {
        const errSpan = document.createElement("span");
        errSpan.className = "etym-empty";
        errSpan.textContent = `Not in database (${lang} words are not in the English-only Kaikki dump).`;
        etymEl.innerHTML = "";
        etymEl.appendChild(errSpan);
    }
}

// --- applyBrightnessFromNode helpers ---

// BFS to compute hop distance from a starting node across all graph edges.
function computeHopDistances(edgesDS, startId) {
    const adjacency = {};
    edgesDS.forEach((e) => {
        if (!adjacency[e.from]) adjacency[e.from] = [];
        if (!adjacency[e.to]) adjacency[e.to] = [];
        adjacency[e.from].push(e.to);
        adjacency[e.to].push(e.from);
    });

    const dist = {};
    const queue = [startId];
    dist[startId] = 0;
    while (queue.length > 0) {
        const cur = queue.shift();
        for (const neighbor of adjacency[cur] || []) {
            if (!(neighbor in dist)) {
                dist[neighbor] = dist[cur] + 1;
                queue.push(neighbor);
            }
        }
    }
    return dist;
}

function buildBrightnessUpdates(baseColors, hopDistances) {
    const updates = [];
    for (const id in baseColors) {
        const hops = hopDistances[id] ?? Infinity;
        const opacity = hops === Infinity ? OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1] : opacityForHops(hops);
        const rgba = colorWithOpacity(baseColors[id], opacity);
        const fontOpacity = opacity;
        updates.push({
            id,
            color: { background: rgba, border: rgba, highlight: { background: rgba, border: rgba } },
            font: { color: `rgba(255,255,255,${fontOpacity})` },
        });
    }
    return updates;
}

function applyBrightnessFromNode(startId, edgesDS) {
    const hopDistances = computeHopDistances(edgesDS, startId);
    const updates = buildBrightnessUpdates(nodeBaseColors, hopDistances);
    nodesDataSet.update(updates);
}

function resetBrightness() {
    const updates = [];
    for (const id in nodeBaseColors) {
        updates.push({ id, color: nodeBaseColors[id], font: { color: "#fff" } });
    }
    nodesDataSet.update(updates);
}

document.getElementById("close-panel").addEventListener("click", () => {
    document.getElementById("detail-panel").hidden = true;
});

document.getElementById("toggle-panel").addEventListener("click", () => {
    const panel = document.getElementById("detail-panel");
    panel.hidden = !panel.hidden;
});

// Zoom controls
function focusNode(nodeId) {
    if (!network || !nodeId) return;
    const pos = network.getPositions([nodeId])[nodeId];
    if (!pos) return;
    network.moveTo({
        position: { x: pos.x, y: pos.y },
        scale: 2.5,
        animation: { duration: 500, easingFunction: "easeInOutQuad" },
    });
    network.selectNodes([nodeId]);
}

document.getElementById("zoom-word").addEventListener("click", () => focusNode(wordNodeId));
document.getElementById("zoom-root").addEventListener("click", () => focusNode(rootNodeId));

document.getElementById("zoom-fit").addEventListener("click", () => {
    if (!network) return;
    network.fit({
        animation: { duration: 500, easingFunction: "easeInOutQuad" },
    });
});

// Etymology link mode: persist preference
const etymLinkSelect = document.getElementById("etym-link-mode");
etymLinkSelect.value = localStorage.getItem("etymLinkMode") || "app";
etymLinkSelect.addEventListener("change", () => {
    localStorage.setItem("etymLinkMode", etymLinkSelect.value);
});

// Delegated click handler for etymology links
document.getElementById("detail-etym").addEventListener("click", (e) => {
    const link = e.target.closest("a.etym-link");
    if (!link) return;
    e.preventDefault();
    const word = link.dataset.word;
    const langCode = link.dataset.langCode;
    const mode = etymLinkSelect.value;

    if (mode === "wikt") {
        const url = word.startsWith("*")
            ? `https://en.wiktionary.org/wiki/Reconstruction:${encodeURIComponent(langCode)}/${encodeURIComponent(word.replace(/^\*/, ""))}`
            : `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
        window.open(url, "_blank", "noopener");
    } else {
        // In-app mode: look up full language name from graph nodes, then load full tree
        if (typeof selectWord === "function") {
            const matchedNode = currentNodes.find(n => n.label === word);
            selectWord(word, matchedNode ? matchedNode.language : undefined);
        }
    }
});
