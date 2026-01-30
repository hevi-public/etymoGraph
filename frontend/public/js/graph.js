const nodes = new vis.DataSet([
    { id: "wine:English", label: "wine\n(English)", color: "#4a90d9", font: { color: "#fff" }, level: 0 },
    { id: "win:Middle English", label: "win\n(Middle English)", color: "#4a90d9", font: { color: "#fff" }, level: 1 },
    { id: "wīn:Old English", label: "wīn\n(Old English)", color: "#4a90d9", font: { color: "#fff" }, level: 2 },
    { id: "*wīną:Proto-Germanic", label: "*wīną\n(Proto-Germanic)", color: "#4a90d9", font: { color: "#fff" }, level: 3 },
    { id: "vīnum:Latin", label: "vīnum\n(Latin)", color: "#d94a4a", font: { color: "#fff" }, level: 4 },
    { id: "*wīnom:Proto-Italic", label: "*wīnom\n(Proto-Italic)", color: "#d94a4a", font: { color: "#fff" }, level: 5 },
    { id: "*wóyh₁nom:PIE", label: "*wóyh₁nom\n(Proto-Indo-European)", color: "#d4a843", font: { color: "#fff" }, level: 6 },
]);

const edges = new vis.DataSet([
    { from: "wine:English", to: "win:Middle English", label: "inherited", arrows: "to" },
    { from: "win:Middle English", to: "wīn:Old English", label: "inherited", arrows: "to" },
    { from: "wīn:Old English", to: "*wīną:Proto-Germanic", label: "inherited", arrows: "to" },
    { from: "*wīną:Proto-Germanic", to: "vīnum:Latin", label: "borrowed", arrows: "to", dashes: true },
    { from: "vīnum:Latin", to: "*wīnom:Proto-Italic", label: "inherited", arrows: "to" },
    { from: "*wīnom:Proto-Italic", to: "*wóyh₁nom:PIE", label: "inherited", arrows: "to" },
]);

const container = document.getElementById("graph");

const options = {
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

new vis.Network(container, { nodes, edges }, options);
