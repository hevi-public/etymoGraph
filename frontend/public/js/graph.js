const graphContainer = document.getElementById("graph");

const LANG_COLORS = {
    germanic: "#5B8DEF",
    romance: "#EF5B5B",
    greek: "#43D9A2",
    pie: "#F5C842",
    slavic: "#CE6BF0",
    celtic: "#FF8C42",
    indoiranian: "#FF6B9D",
    semitic: "#00BCD4",
    uralic: "#8BC34A",
    other: "#A0A0B8",
};

function langColor(lang) {
    if (/english|german|norse|dutch|frisian|gothic|proto-germanic|proto-west germanic|saxon|scots|yiddish|afrikaans|plautdietsch|limburgish|luxembourgish|cimbrian|alemannic|bavarian|vilamovian|saterland/i.test(lang)) return LANG_COLORS.germanic;
    if (/latin|italic|french|spanish|portuguese|romanian|proto-italic|catalan|occitan|sardinian|galician|venetian|sicilian|neapolitan|asturian/i.test(lang)) return LANG_COLORS.romance;
    if (/greek/i.test(lang)) return LANG_COLORS.greek;
    if (/proto-indo-european/i.test(lang)) return LANG_COLORS.pie;
    if (/russian|polish|czech|slovak|serbian|croatian|bulgarian|ukrainian|slovene|proto-slavic|old church slavonic|belarusian|macedonian|sorbian/i.test(lang)) return LANG_COLORS.slavic;
    if (/irish|welsh|scottish gaelic|breton|cornish|manx|proto-celtic|old irish/i.test(lang)) return LANG_COLORS.celtic;
    if (/sanskrit|hindi|persian|urdu|bengali|punjabi|avestan|pali|proto-indo-iranian/i.test(lang)) return LANG_COLORS.indoiranian;
    if (/arabic|hebrew|aramaic|akkadian|proto-semitic/i.test(lang)) return LANG_COLORS.semitic;
    if (/finnish|hungarian|estonian|proto-uralic|proto-finnic/i.test(lang)) return LANG_COLORS.uralic;
    return LANG_COLORS.other;
}

const EDGE_LABELS = { inh: "inherited", bor: "borrowed", der: "derived", cog: "cognate" };

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

const graphOptions = {
    layout: {
        improvedLayout: true,
    },
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
        forceAtlas2Based: {
            gravitationalConstant: -80,
            centralGravity: 0.01,
            springLength: 150,
            springConstant: 0.02,
            damping: 0.4,
        },
        stabilization: false,
    },
    interaction: {
        zoomView: false,
        dragView: true,
        hover: true,
    },
};

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let currentNodes = [];
let nodeBaseColors = {};  // id → hex color
let rootNodeId = null;   // etymological root (deepest ancestor)
let wordNodeId = null;   // searched word

function updateGraph(data) {
    if (network) {
        network.destroy();
    }
    currentNodes = data.nodes;

    // The searched word has level 0
    const wordNode = data.nodes.find((n) => n.level === 0);
    wordNodeId = wordNode ? wordNode.id : null;

    // The etymological root is the node with the lowest (most negative) level
    const etymRoot = data.nodes.reduce((min, n) => (n.level < min.level ? n : min), data.nodes[0]);
    rootNodeId = etymRoot ? etymRoot.id : null;

    nodeBaseColors = {};
    nodesDataSet = new vis.DataSet(
        data.nodes.map((n) => {
            const isRoot = n.id === rootNodeId;
            const color = langColor(n.language);
            nodeBaseColors[n.id] = color;
            return {
                ...n,
                label: `${n.label}\n(${n.language})`,
                color,
                // Pin the root node to the center
                mass: isRoot ? 5 : Math.max(1, 5 / Math.pow(2, Math.abs(n.level))),
                ...(isRoot ? { x: 0, y: 0, fixed: { x: true, y: true } } : {}),
            };
        })
    );
    const nodes = nodesDataSet;
    edgesDataSet = new vis.DataSet(
        data.edges.map((e) => ({
            ...e,
            label: EDGE_LABELS[e.label] || e.label,
            arrows: "to",
            dashes: e.label === "bor" || e.label === "cog",
            color: e.label === "cog" ? { color: "#F5C842", highlight: "#FFE066" } : undefined,
        }))
    );
    const edges = edgesDataSet;
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);

    // Start view centered on the root node
    network.moveTo({ position: { x: 0, y: 0 }, scale: 1, animation: false });

    // Trackpad: pinch zooms (ctrlKey), two-finger scroll pans
    graphContainer.addEventListener("wheel", (e) => {
        e.preventDefault();
        if (e.ctrlKey) {
            // Pinch gesture — macOS sets ctrlKey for pinch
            const scale = network.getScale();
            const newScale = scale * (1 - e.deltaY * 0.01);
            network.moveTo({ scale: Math.max(0.1, Math.min(5, newScale)), animation: false });
        } else {
            // Two-finger scroll — pan
            const pos = network.getViewPosition();
            network.moveTo({
                position: { x: pos.x + e.deltaX, y: pos.y + e.deltaY },
                animation: false,
            });
        }
    }, { passive: false });

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

function buildConnectionsPanel(nodeId) {
    const container = document.getElementById("detail-connections");
    container.innerHTML = "";

    if (!edgesDataSet) return;

    const CONNECTION_SECTIONS = {
        inh: "Inherited",
        bor: "Borrowed",
        der: "Derived",
        cog: "Cognate",
    };

    // Collect edges from/to this node, grouped by original label
    const grouped = {};
    edgesDataSet.forEach((e) => {
        // e.label is the display label ("inherited"), we need the raw type
        const rawType = Object.keys(EDGE_LABELS).find((k) => EDGE_LABELS[k] === e.label) || e.label;
        let targetId = null;
        if (e.from === nodeId) targetId = e.to;
        else if (e.to === nodeId) targetId = e.from;
        if (!targetId) return;

        if (!grouped[rawType]) grouped[rawType] = [];
        grouped[rawType].push(targetId);
    });

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

async function showDetail(word, lang) {
    const panel = document.getElementById("detail-panel");
    const wordEl = document.getElementById("detail-word");
    const langEl = document.getElementById("detail-lang");
    const posEl = document.getElementById("detail-pos");
    const ipaEl = document.getElementById("detail-ipa");
    const defsEl = document.getElementById("detail-defs");
    const etymEl = document.getElementById("detail-etym");

    wordEl.textContent = word;
    langEl.textContent = lang;
    posEl.textContent = "";
    ipaEl.textContent = "";
    defsEl.innerHTML = "";
    etymEl.textContent = "";
    panel.hidden = false;

    // Build connections from graph edges
    const nodeId = `${word}:${lang}`;
    buildConnectionsPanel(nodeId);

    try {
        const data = await getWord(word, lang);
        posEl.textContent = data.pos || "";
        ipaEl.textContent = data.pronunciation || "";
        defsEl.innerHTML = "";
        (data.definitions || []).forEach((d) => {
            const li = document.createElement("li");
            li.textContent = d;
            defsEl.appendChild(li);
        });
        etymEl.textContent = data.etymology_text || "No etymology text available.";
    } catch (e) {
        etymEl.textContent = `Not in database (${lang} words are not in the English-only Kaikki dump).`;
    }
}

function applyBrightnessFromNode(startId, edgesDataSet) {
    // BFS to compute hop distance from the selected node
    const adjacency = {};
    edgesDataSet.forEach((e) => {
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

    const updates = [];
    for (const id in nodeBaseColors) {
        const hops = dist[id] ?? Infinity;
        const opacity = hops === Infinity ? OPACITY_BY_HOP[OPACITY_BY_HOP.length - 1] : opacityForHops(hops);
        const rgba = colorWithOpacity(nodeBaseColors[id], opacity);
        const fontOpacity = opacity;
        updates.push({
            id,
            color: { background: rgba, border: rgba, highlight: { background: rgba, border: rgba } },
            font: { color: `rgba(255,255,255,${fontOpacity})` },
        });
    }
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
