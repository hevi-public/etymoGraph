/**
 * G6 v5 renderer adapter — experimental WebGL-capable graph renderer.
 * Loaded alongside vis.js; activated when user selects "G6 v5" in the
 * renderer dropdown. G6 script is lazy-loaded on first use.
 *
 * Phase 1: force-directed layout, basic node/edge styling, click interaction.
 * See SPC-00005 for the full feature roadmap.
 */

/* global classifyLang, EDGE_LABELS, findRootAndWordNodes, showDetail, desaturateColor, UNCERTAINTY_DESATURATION */

let _g6LoadPromise = null;

/** Dynamically load the G6 v5 script from CDN. Cached after first load. */
function _loadG6Script() {
    if (window.G6) return Promise.resolve();
    if (_g6LoadPromise) return _g6LoadPromise;

    _g6LoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/@antv/g6@5/dist/g6.min.js";
        script.onload = () => resolve();
        script.onerror = () => {
            _g6LoadPromise = null;
            reject(new Error("Failed to load G6 from CDN"));
        };
        document.head.appendChild(script);
    });
    return _g6LoadPromise;
}

// eslint-disable-next-line no-unused-vars
function createG6Adapter(container) {
    let graph = null;
    let nodeDataMap = {};  // id -> { word, language, level }

    function getNodeColor(lang, uncertainty) {
        const { color } = classifyLang(lang);
        if (uncertainty && uncertainty.is_uncertain) {
            return desaturateColor(color, UNCERTAINTY_DESATURATION);
        }
        return color;
    }

    async function render(data) {
        await _loadG6Script();

        if (graph) {
            graph.destroy();
            graph = null;
        }

        // Clear container
        container.innerHTML = "";

        const { rootNodeId } = findRootAndWordNodes(data.nodes);

        // Build node data map for click handler
        nodeDataMap = {};
        const g6Nodes = data.nodes.map((n) => {
            const isRoot = n.id === rootNodeId;
            const color = getNodeColor(n.language, n.uncertainty);
            nodeDataMap[n.id] = { word: n.label, language: n.language, level: n.level };

            return {
                id: n.id,
                data: {
                    label: n.label,
                    language: n.language,
                    level: n.level,
                    isRoot,
                    color,
                    edgeType: null,
                },
            };
        });

        const g6Edges = data.edges.map((e) => ({
            source: e.from,
            target: e.to,
            data: {
                edgeType: e.label,
                edgeLabel: EDGE_LABELS[e.label] || e.label,
            },
        }));

        graph = new window.G6.Graph({
            container,
            width: container.clientWidth,
            height: container.clientHeight,
            autoFit: "view",

            data: { nodes: g6Nodes, edges: g6Edges },

            node: {
                type: "rect",
                style: {
                    size: function (d) {
                        return d.data?.isRoot ? [130, 42] : [110, 36];
                    },
                    fill: function (d) {
                        return d.data?.color || "#A0A0B8";
                    },
                    stroke: function (d) {
                        return d.data?.isRoot ? "#FFD700" : "transparent";
                    },
                    lineWidth: function (d) {
                        return d.data?.isRoot ? 3 : 0;
                    },
                    radius: 4,
                    shadowColor: function (d) {
                        return d.data?.isRoot ? "rgba(255, 215, 0, 0.5)" : "transparent";
                    },
                    shadowBlur: function (d) {
                        return d.data?.isRoot ? 20 : 0;
                    },
                    labelText: function (d) {
                        var label = d.data?.label || d.id;
                        var lang = d.data?.language || "";
                        return label + "\n(" + lang + ")";
                    },
                    labelFill: "#fff",
                    labelFontSize: 12,
                    labelPlacement: "center",
                },
            },

            edge: {
                type: "line",
                style: {
                    stroke: function (d) {
                        var type = d.data?.edgeType;
                        if (type === "cog") return "#F5C842";
                        if (type === "component" || type === "mention") return "#888888";
                        return "#555555";
                    },
                    lineWidth: 1.5,
                    endArrow: true,
                    lineDash: function (d) {
                        var type = d.data?.edgeType;
                        if (type === "bor" || type === "cog" || type === "component" || type === "mention") {
                            return [6, 4];
                        }
                        return [0, 0];
                    },
                    labelText: function (d) {
                        return d.data?.edgeLabel || "";
                    },
                    labelFill: "#999",
                    labelFontSize: 10,
                },
            },

            layout: {
                type: "d3-force",
                preventOverlap: true,
                nodeSize: 40,
                link: {
                    distance: 150,
                },
                charge: {
                    strength: -300,
                    distanceMax: 600,
                },
                collide: {
                    radius: 30,
                    strength: 0.7,
                },
            },

            behaviors: [
                "drag-canvas",
                "zoom-canvas",
                "drag-element",
            ],
        });

        await graph.render();

        // Click handler: show detail panel on node click
        graph.on("node:click", function (event) {
            var nodeId = event.target.id;
            var info = nodeDataMap[nodeId];
            if (info) {
                showDetail(info.word, info.language);
            }
            // Animate to clicked node
            graph.focusElement(nodeId, { duration: 400, easing: "ease-in-out" });
        });

        // Click on canvas background: close detail panel
        graph.on("canvas:click", function () {
            var panel = document.getElementById("detail-panel");
            if (panel) panel.hidden = true;
        });
    }

    function destroy() {
        if (graph) {
            graph.destroy();
            graph = null;
        }
        nodeDataMap = {};
        container.innerHTML = "";
    }

    function selectNode(nodeId) {
        if (!graph) return;
        var info = nodeDataMap[nodeId];
        if (info) {
            showDetail(info.word, info.language);
        }
        graph.focusElement(nodeId, { duration: 400, easing: "ease-in-out" });
    }

    /** Stop layout animation without destroying the graph (preserves canvas state). */
    function stopLayout() {
        if (graph) {
            try { graph.stopLayout(); } catch (_) { /* layout may already be stopped */ }
        }
    }

    /** Resize graph to match container dimensions (call after container becomes visible). */
    function resize() {
        if (graph) {
            var w = container.clientWidth;
            var h = container.clientHeight;
            if (w > 0 && h > 0) {
                graph.resize(w, h);
            }
        }
    }

    return {
        type: "g6",
        render: render,
        destroy: destroy,
        stopLayout: stopLayout,
        resize: resize,
        selectNode: selectNode,
        getAvailableLayouts: function () { return ["force-directed"]; },
        getCurrentLayout: function () { return "force-directed"; },
    };
}
