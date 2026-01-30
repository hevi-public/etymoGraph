const graphContainer = document.getElementById("graph");

const LANG_COLORS = {
    germanic: "#4a90d9",
    romance: "#d94a4a",
    greek: "#4abd8c",
    pie: "#d4a843",
    other: "#888",
};

function langColor(lang) {
    if (/english|german|norse|dutch|frisian|gothic|proto-germanic/i.test(lang)) return LANG_COLORS.germanic;
    if (/latin|italic|french|spanish|portuguese|romanian|proto-italic/i.test(lang)) return LANG_COLORS.romance;
    if (/greek/i.test(lang)) return LANG_COLORS.greek;
    if (/proto-indo-european/i.test(lang)) return LANG_COLORS.pie;
    return LANG_COLORS.other;
}

const EDGE_LABELS = { inh: "inherited", bor: "borrowed", der: "derived" };

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
        stabilization: {
            iterations: 200,
        },
    },
    interaction: {
        zoomView: true,
        dragView: true,
        hover: true,
    },
};

let network = null;
let currentNodes = [];

function updateGraph(data) {
    if (network) {
        network.destroy();
    }
    currentNodes = data.nodes;

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
            dashes: e.label === "bor",
        }))
    );
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);

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
