const graphContainer = document.getElementById("graph");

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
        font: { size: 13, multi: true },
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
    const nodes = new vis.DataSet(data.nodes);
    const edges = new vis.DataSet(data.edges);
    network = new vis.Network(graphContainer, { nodes, edges }, graphOptions);
}
