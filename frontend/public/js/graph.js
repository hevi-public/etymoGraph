/* global
   classifyLang, getLangFamily, langColor, LANG_FAMILIES, DEFAULT_FAMILY_COLOR,
   EDGE_LABELS, desaturateColor, colorWithOpacity, extractOpacity,
   OPACITY_BY_HOP, opacityForHops, UNCERTAINTY_DESATURATION,
   ERA_TIERS, getEraTier, groupNodesByTierAndFamily, assignFamilyClusterPositions,
   computeTreePositions, findRootAndWordNodes,
   getWord
*/

const graphContainer = document.getElementById("graph");

// --- Pure utility functions extracted from formatEtymologyText ---

function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Build lookup from etymology templates: word -> {word, lang_code} for linkable terms.
 * Processes cognates first, then ancestry types (inh/bor/der) so ancestry takes
 * priority when the same word appears in both template types.
 * @param {Array<{name: string, args: Object}>} templates - Kaikki etymology_templates array
 * @returns {Object<string, {word: string, lang_code: string}>} Word-to-template-info lookup
 */
function buildTemplateLookup(templates) {
    const lookup = {};
    if (!templates || !templates.length) return lookup;
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

/**
 * Replace known etymology words in pre-escaped HTML with clickable links.
 * @param {string} escaped - HTML-escaped etymology text
 * @param {Object<string, {word: string, lang_code: string}>} templateLookup
 * @returns {string} HTML string with linked etymology terms
 */
function linkifyEtymologyText(escaped, templateLookup) {
    if (!Object.keys(templateLookup).length) return escaped;
    const words = Object.keys(templateLookup).sort((a, b) => b.length - a.length);
    const pattern = new RegExp("(?<![\\w*])(" + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")(?!\\w)", "g");
    return escaped.replace(pattern, (match) => {
        const entry = templateLookup[match];
        if (!entry) return match;
        return `<a class="etym-link" href="#" data-word="${escapeHtml(entry.word)}" data-lang-code="${escapeHtml(entry.lang_code)}">${match}</a>`;
    });
}

/**
 * Split etymology text into tree, prose, and cognate sections.
 * @param {string} text - Raw etymology_text from Kaikki
 * @returns {{tree: string, prose: string, cognates: string}} Separated sections
 */
function splitEtymologySections(text) {
    let tree = "";
    let prose = "";
    let cognates = "";

    const lines = text.split("\n");
    let section = "auto";

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
    return "<div class=\"etym-chain\">" + steps.join(" <span class=\"etym-arrow\">→</span> ") + "</div>";
}

function renderEtymologyCognates(cognatesText, templateLookup) {
    const items = cognatesText.split("\n").map((c) => c.replace(/^\*\s*/, "").trim()).filter(Boolean);
    let html = "<details class=\"etym-cognates\"><summary>Cognates (" + items.length + ")</summary><p>";
    html += items.map(c => {
        const glossMatch = c.match(/^(.+?)\s+(\(".+"\))$/);
        if (glossMatch) {
            const before = glossMatch[1];
            const gloss = glossMatch[2];
            const ls = before.lastIndexOf(" ");
            if (ls > 0) {
                const word = before.slice(ls + 1);
                const lang = before.slice(0, ls);
                return escapeHtml(lang) + " " + makeEtymLink(word, word, templateLookup) + " " + "<span class=\"etym-gloss\">" + escapeHtml(gloss) + "</span>";
            }
            return makeEtymLink(before, before, templateLookup) + " " + "<span class=\"etym-gloss\">" + escapeHtml(gloss) + "</span>";
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

function formatEtymologyText(text, templates) {
    if (!text) return "<span class=\"etym-empty\">No etymology text available.</span>";

    const templateLookup = buildTemplateLookup(templates);
    const { tree, prose, cognates } = splitEtymologySections(text);

    let html = "";

    if (tree) {
        html += renderEtymologyChain(tree, templateLookup);
    }

    if (prose) {
        let escaped = escapeHtml(prose);
        escaped = escaped.replace(/\b(from|From|of)\s+((?:Proto-|Middle |Old |Late |Ancient |Medieval |Vulgar |Biblical |Classical )*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
            "$1 <strong>$2</strong>");
        escaped = escaped.replace(/\(("[^"]*")\)/g, "<span class=\"etym-gloss\">($1)</span>");
        escaped = linkifyEtymologyText(escaped, templateLookup);
        html += "<p class=\"etym-prose\">" + escaped + "</p>";
    }

    if (cognates) {
        html += renderEtymologyCognates(cognates, templateLookup);
    }

    return html || "<span class=\"etym-empty\">No etymology text available.</span>";
}

// --- vis.js uncertainty styling ---

const UNCERTAINTY_BORDER_DASHES = [5, 5];

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

function rootNodeStyle(bgColor) {
    return {
        font: { size: 16, multi: true, color: "#fff", bold: { size: 18 } },
        margin: 14,
        borderWidth: 3,
        color: {
            background: bgColor,
            border: "#FFD700",
            highlight: { background: bgColor, border: "#FFD700" },
            hover: { background: bgColor, border: "#FFD700" },
        },
        shadow: {
            enabled: true,
            color: "rgba(255, 215, 0, 0.5)",
            size: 20,
            x: 0,
            y: 0,
        },
    };
}

// --- vis.js Graph Options & Layout Strategies ---

/**
 * Build vis.js graph options by deep-merging overrides into a base config.
 */
function baseGraphOptions(overrides) {
    const base = {
        layout: {
            randomSeed: 42,
            improvedLayout: true
        },
        edges: {
            color: { color: "#555", highlight: "#aaa" },
            font: { color: "#999", size: 11, strokeWidth: 0 },
            smooth: { type: "continuous" },
            width: 3,
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
            minVelocity: 2.0,
            maxVelocity: 50,
        },
        interaction: {
            zoomView: false,
            dragView: true,
            hover: true,
        },
    };
    for (const [section, values] of Object.entries(overrides)) {
        if (typeof values === "object" && !Array.isArray(values) && base[section]) {
            base[section] = { ...base[section], ...values };
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
                        gravitationalConstant: -350,
                        centralGravity: 0.025,
                        springLength: 120,
                        springConstant: 0.06,
                        damping: 0.5,
                        avoidOverlap: 0.5,
                    },
                },
            });
        },
        buildVisNodes(nodes, rootId) {
            const baseColors = {};
            const visNodes = nodes.map((n) => {
                const isRoot = n.id === rootId;
                const { family, color } = classifyLang(n.language);
                baseColors[n.id] = color;
                const style = uncertaintyNodeStyle(color, n.uncertainty);
                const bgColor = style.color?.background || color;
                const root = isRoot ? rootNodeStyle(bgColor) : {};
                return {
                    ...n,
                    family,
                    label: `${n.label}\n(${n.language})`,
                    ...style,
                    ...root,
                    mass: isRoot ? 4 : Math.max(1, 4 / Math.pow(2, Math.abs(n.level))),
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
        buildVisNodes(nodes, rootId) {
            const baseColors = {};
            const tierFamilyGroups = groupNodesByTierAndFamily(nodes);
            const nodeXPositions = assignFamilyClusterPositions(tierFamilyGroups);
            const visNodes = nodes.map((n) => {
                const isRoot = n.id === rootId;
                const { family, color } = classifyLang(n.language);
                baseColors[n.id] = color;
                const tier = getEraTier(n.language);
                const yPos = ERA_TIERS[tier].y;
                const style = uncertaintyNodeStyle(color, n.uncertainty);
                const bgColor = style.color?.background || color;
                const root = isRoot ? rootNodeStyle(bgColor) : {};
                return {
                    ...n,
                    family,
                    label: `${n.label}\n(${n.language})`,
                    ...style,
                    ...root,
                    mass: 1,
                    x: nodeXPositions[n.id] || 0,
                    y: yPos,
                    fixed: { y: true },
                };
            });
            return { visNodes, nodeBaseColors: baseColors };
        },
        buildExtraEdges(nodes) {
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
if (!LAYOUTS[currentLayout]) currentLayout = "era-layered";

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let currentNodes = [];
let nodeBaseColors = {};
let edgeBaseColors = {};
let rootNodeId = null;
let wordNodeId = null;

// --- Performance thresholds (SPC-00004) ---
const LARGE_GRAPH_THRESHOLD = 200;
const VERY_LARGE_GRAPH_THRESHOLD = 1000;
const LOD_SCALE_THRESHOLD = 0.4;
const CLUSTER_THRESHOLD = 0.25;
const DECLUSTER_THRESHOLD = 0.35;
const CLUSTER_MIN_NODES = 500;

let lodActive = false;
let activeClusters = [];

/**
 * Mutate vis.js options for large-graph performance (R1, R4, R7).
 */
function applyPerformanceOverrides(options, nodeCount) {
    if (nodeCount > LARGE_GRAPH_THRESHOLD) {
        options.edges.smooth = false;
        options.layout.improvedLayout = false;
    }
    if (nodeCount > VERY_LARGE_GRAPH_THRESHOLD) {
        options.physics.solver = "barnesHut";
        options.physics.barnesHut = { theta: 0.8 };
    }
}

/**
 * Handle level-of-detail label visibility based on zoom scale (R2).
 */
function handleZoomLOD(scale) {
    if (!network) return;
    if (scale < LOD_SCALE_THRESHOLD && !lodActive) {
        network.setOptions({
            nodes: { font: { color: "transparent" } },
            edges: { font: { color: "transparent" } },
        });
        lodActive = true;
    } else if (scale >= LOD_SCALE_THRESHOLD && lodActive) {
        network.setOptions({
            nodes: { font: { color: "#fff" } },
            edges: { font: { color: "#999" } },
        });
        lodActive = false;
    }
}

/**
 * Handle zoom-based clustering by language family (R3).
 */
function handleZoomClustering(scale) {
    if (!network || currentNodes.length < CLUSTER_MIN_NODES) return;

    if (scale < CLUSTER_THRESHOLD && activeClusters.length === 0) {
        const familyCounts = {};
        nodesDataSet.forEach((n) => {
            const family = n.family || "other";
            familyCounts[family] = (familyCounts[family] || 0) + 1;
        });

        for (const [family, count] of Object.entries(familyCounts)) {
            if (count < 2) continue;
            const clusterId = `cluster:${family}`;
            const familyEntry = LANG_FAMILIES.find(([f]) => f === family);
            const displayName = familyEntry ? familyEntry[1] : "Other";
            const familyColor = familyEntry ? familyEntry[2] : DEFAULT_FAMILY_COLOR;

            network.cluster({
                joinCondition: (nodeOptions) => (nodeOptions.family || "other") === family,
                clusterNodeProperties: {
                    id: clusterId,
                    label: `${displayName} (${count})`,
                    shape: "dot",
                    size: Math.sqrt(count) * 5,
                    color: familyColor,
                    font: { color: "#fff" },
                },
            });
            activeClusters.push(clusterId);
        }
    } else if (scale > DECLUSTER_THRESHOLD && activeClusters.length > 0) {
        for (const id of activeClusters) {
            try {
                network.openCluster(id);
            } catch {
                // Cluster may already be gone
            }
        }
        activeClusters = [];
    }
}

// --- updateGraph helpers ---

function buildVisEdges(edges) {
    const degree = {};
    for (const e of edges) {
        degree[e.from] = (degree[e.from] || 0) + 1;
        degree[e.to] = (degree[e.to] || 0) + 1;
    }

    const BASE_LENGTH = 110;
    const LENGTH_SCALE = 50;
    const BASE_SPRING = 0.1;

    return edges.map((e) => {
        const isMention = e.label === "component" || e.label === "mention";
        const dFrom = degree[e.from] || 1;
        const dTo = degree[e.to] || 1;
        const combined = dFrom + dTo;
        const maxDeg = Math.max(dFrom, dTo);

        const edgeOpacity = Math.max(0.2, 1.0 / Math.log2(2 + maxDeg));
        const hideLabel = dFrom > 5 && dTo > 5;

        let baseColor, highlightColor;
        if (e.label === "cog") {
            baseColor = colorWithOpacity("#F5C842", edgeOpacity);
            highlightColor = "#FFE066";
        } else if (isMention) {
            baseColor = colorWithOpacity("#888888", edgeOpacity);
            highlightColor = "#aaaaaa";
        } else {
            baseColor = colorWithOpacity("#555555", edgeOpacity);
            highlightColor = "#aaaaaa";
        }

        return {
            ...e,
            rawType: e.label,
            label: hideLabel ? "" : (EDGE_LABELS[e.label] || e.label),
            arrows: "to",
            dashes: e.label === "bor" || e.label === "cog" || isMention,
            color: { color: baseColor, highlight: highlightColor },
            length: BASE_LENGTH + LENGTH_SCALE * Math.log2(1 + combined),
            springConstant: BASE_SPRING / Math.log2(1 + maxDeg),
        };
    });
}

// eslint-disable-next-line no-unused-vars
function updateGraph(data) {
    if (network) {
        network.destroy();
    }
    currentNodes = data.nodes;
    lodActive = false;
    activeClusters = [];

    const found = findRootAndWordNodes(data.nodes);
    rootNodeId = found.rootNodeId;
    wordNodeId = found.wordNodeId;

    const layout = LAYOUTS[currentLayout];
    const options = layout.getGraphOptions();
    applyPerformanceOverrides(options, data.nodes.length);
    const { visNodes, nodeBaseColors: colors } = layout.buildVisNodes(data.nodes, rootNodeId);
    nodeBaseColors = colors;

    // Tree-based initial positioning for force-directed layout
    if (currentLayout === "force-directed" && data.edges.length > 0) {
        const positions = computeTreePositions(data.nodes, data.edges, rootNodeId);
        const scale = 0.35;
        for (const vn of visNodes) {
            if (vn.fixed?.x && vn.fixed?.y) continue;
            const pos = positions[vn.id];
            if (pos) { vn.x = pos.x * scale; vn.y = pos.y * scale; }
        }
    }

    nodesDataSet = new vis.DataSet(visNodes);
    const nodes = nodesDataSet;
    const extraEdges = layout.buildExtraEdges(data.nodes);
    const allEdges = [...buildVisEdges(data.edges), ...extraEdges];
    edgesDataSet = new vis.DataSet(allEdges);
    const edges = edgesDataSet;

    edgeBaseColors = {};
    edgesDataSet.forEach((e) => {
        if (e.color) {
            edgeBaseColors[e.id] = {
                color: e.color.color || e.color,
                highlight: e.color.highlight || e.color.color || e.color,
            };
        } else {
            edgeBaseColors[e.id] = { color: "#555", highlight: "#aaa" };
        }
    });
    network = new vis.Network(graphContainer, { nodes, edges }, options);

    // Expose network instance for E2E tests and zoom controls
    window.__etymoNetwork = network;
    window.__etymoNodesDS = nodesDataSet;

    if (layout.onBeforeDrawing) {
        network.on("beforeDrawing", (ctx) => layout.onBeforeDrawing(network, ctx));
    }

    const view = layout.getInitialView(data.nodes, wordNodeId, rootNodeId);
    network.moveTo({ ...view, animation: false });

    network.on("click", (params) => {
        if (params.nodes.length > 0) {
            const clickedId = params.nodes[0];

            if (network.isCluster(clickedId)) {
                try {
                    network.openCluster(clickedId);
                } catch {
                    // Cluster may already be gone
                }
                activeClusters = activeClusters.filter((id) => id !== clickedId);
                return;
            }

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
            resetBrightness();
        }
    });

    // R5: Freeze physics after stabilization to reduce CPU usage
    network.on("stabilized", () => {
        network.setOptions({ physics: { enabled: false } });
    });
    network.on("dragStart", () => {
        network.setOptions({ physics: { enabled: true } });
    });
    network.on("dragEnd", () => {
        setTimeout(() => {
            if (network) network.setOptions({ physics: { enabled: false } });
        }, 500);
    });
}

// Trackpad: pinch zooms (ctrlKey), two-finger scroll pans
graphContainer.addEventListener("wheel", (e) => {
    if (!network) return;
    e.preventDefault();
    if (e.ctrlKey) {
        const scale = network.getScale();
        const newScale = Math.max(0.1, Math.min(5, scale * (1 - e.deltaY * 0.01)));
        network.moveTo({ scale: newScale, animation: false });
        handleZoomLOD(newScale);
        handleZoomClustering(newScale);
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
    renderUncertaintyBadge(null);
    panel.hidden = false;

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
    } catch {
        const errSpan = document.createElement("span");
        errSpan.className = "etym-empty";
        errSpan.textContent = `Not in database (${lang} words are not in the English-only Kaikki dump).`;
        etymEl.innerHTML = "";
        etymEl.appendChild(errSpan);
    }
}

// --- applyBrightnessFromNode helpers ---

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
        const isRoot = id === rootNodeId;
        const borderColor = isRoot ? colorWithOpacity("#FFD700", opacity) : rgba;
        updates.push({
            id,
            color: {
                background: rgba, border: borderColor,
                highlight: { background: rgba, border: borderColor },
                hover: { background: rgba, border: borderColor },
            },
            font: { color: `rgba(255,255,255,${fontOpacity})` },
        });
    }
    return updates;
}

function buildEdgeBrightnessUpdates(edgesDS, hopDistances) {
    const updates = [];
    edgesDS.forEach((e) => {
        if (e.hidden) return;
        const fromHops = hopDistances[e.from] ?? Infinity;
        const toHops = hopDistances[e.to] ?? Infinity;
        const hopOpacity = opacityForHops(Math.min(fromHops, toHops));
        const base = edgeBaseColors[e.id] || { color: "rgba(85,85,85,1)", highlight: "rgba(170,170,170,1)" };
        const baseOpacity = extractOpacity(base.color);
        const baseHighOpacity = extractOpacity(base.highlight);
        updates.push({
            id: e.id,
            color: {
                color: colorWithOpacity(base.color, baseOpacity * hopOpacity),
                highlight: colorWithOpacity(base.highlight, Math.min(1, baseHighOpacity * (hopOpacity + 0.2))),
            },
        });
    });
    return updates;
}

function applyBrightnessFromNode(startId, edgesDS) {
    const hopDistances = computeHopDistances(edgesDS, startId);
    const updates = buildBrightnessUpdates(nodeBaseColors, hopDistances);
    nodesDataSet.update(updates);
    const edgeUpdates = buildEdgeBrightnessUpdates(edgesDS, hopDistances);
    edgesDS.update(edgeUpdates);
}

function resetBrightness() {
    const updates = [];
    for (const id in nodeBaseColors) {
        const color = nodeBaseColors[id];
        const isRoot = id === rootNodeId;
        updates.push({
            id,
            color: isRoot ? rootNodeStyle(color).color : color,
            font: { color: "#fff" },
        });
    }
    nodesDataSet.update(updates);

    if (edgesDataSet) {
        const edgeUpdates = [];
        for (const id in edgeBaseColors) {
            const base = edgeBaseColors[id];
            edgeUpdates.push({
                id,
                color: { color: base.color, highlight: base.highlight },
            });
        }
        edgesDataSet.update(edgeUpdates);
    }
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
        if (typeof selectWord === "function") {
            const matchedNode = currentNodes.find(n => n.label === word);
            selectWord(word, matchedNode ? matchedNode.language : undefined);
        }
    }
});

// Expose internals for unit testing (SPC-00004)
if (typeof window !== "undefined") {
    window.applyPerformanceOverrides = applyPerformanceOverrides;
    window.handleZoomLOD = handleZoomLOD;
    window.handleZoomClustering = handleZoomClustering;
    window.baseGraphOptions = baseGraphOptions;
    window.LAYOUTS = LAYOUTS;
    window.LOD_SCALE_THRESHOLD = LOD_SCALE_THRESHOLD;
    window.CLUSTER_THRESHOLD = CLUSTER_THRESHOLD;
    window.DECLUSTER_THRESHOLD = DECLUSTER_THRESHOLD;
    window.CLUSTER_MIN_NODES = CLUSTER_MIN_NODES;
    window.LARGE_GRAPH_THRESHOLD = LARGE_GRAPH_THRESHOLD;
    window.VERY_LARGE_GRAPH_THRESHOLD = VERY_LARGE_GRAPH_THRESHOLD;
}
