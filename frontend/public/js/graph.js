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

const graphOptions = {
    layout: {
        improvedLayout: true,
    },
    edges: {
        color: { color: "#555", highlight: "#aaa" },
        font: { color: "#999", size: 11 },
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
let currentNodes = [];
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

    const nodes = new vis.DataSet(
        data.nodes.map((n) => ({
            ...n,
            label: `${n.label}\n(${n.language})`,
            color: langColor(n.language),
        }))
    );
    const edges = new vis.DataSet(
        data.edges.map((e) => ({
            ...e,
            label: EDGE_LABELS[e.label] || e.label,
            arrows: "to",
            dashes: e.label === "bor" || e.label === "cog",
            color: e.label === "cog" ? { color: "#F5C842", highlight: "#FFE066" } : undefined,
        }))
    );
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);

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
            const nodeId = params.nodes[0];
            const node = currentNodes.find((n) => n.id === nodeId);
            if (node) {
                showDetail(node.label, node.language);
            }
        }
    });
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
        scale: 1.2,
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
