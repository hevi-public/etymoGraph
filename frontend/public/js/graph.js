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

const graphOptions = {
    layout: {
        hierarchical: {
            direction: "UD",
            sortMethod: "directed",
            levelSeparation: 100,
            nodeSpacing: 150,
        },
    },
    edges: {
        color: { color: "#555", highlight: "#aaa" },
        font: { color: "#999", size: 11 },
        smooth: { type: "cubicBezier" },
    },
    nodes: {
        shape: "box",
        borderWidth: 0,
        font: { size: 13, multi: true, color: "#fff" },
        margin: 10,
    },
    physics: false,
    interaction: {
        zoomView: true,
        dragView: true,
    },
};

let network = null;

function updateGraph(data) {
    if (network) {
        network.destroy();
    }
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
            arrows: "to",
            dashes: e.label === "bor",
        }))
    );
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);
}
