/**
 * G6 v5 concept map adapter — renders phonetic similarity graphs using G6.
 * Activated when user selects "G6 v5" in the renderer dropdown while in concept view.
 * Reuses _loadG6Script() from g6-adapter.js (lazy CDN load).
 *
 * Basic implementation: full re-render on edge updates, uniform phonetic edge width.
 * Advanced features (similarity-scaled edges, highlight dimming, zoom LOD) deferred.
 */

/* global _loadG6Script, langColor, showDetail, showViewInEtymologyButton, filterPhoneticEdges */

// eslint-disable-next-line no-unused-vars
function createG6ConceptAdapter(container) {
    let graph = null;
    let nodeDataMap = {};  // id -> { word, lang }
    let _allNodes = [];    // cached for re-render on edge updates

    async function render(words, etymologyEdges) {
        await _loadG6Script();

        if (graph) {
            graph.destroy();
            graph = null;
        }
        container.innerHTML = "";

        nodeDataMap = {};
        _allNodes = [];

        const g6Nodes = words.map(function (w) {
            var color = langColor(w.lang);
            nodeDataMap[w.id] = { word: w.word, lang: w.lang };
            _allNodes.push({ id: w.id });
            return {
                id: w.id,
                data: {
                    label: w.word,
                    lang: w.lang,
                    color: color,
                },
            };
        });

        var showEtym = document.getElementById("show-etymology-edges");
        var includeEtym = showEtym && showEtym.checked;
        var g6Edges = [];
        if (includeEtym) {
            g6Edges = etymologyEdges.map(function (e) {
                return {
                    source: e.source,
                    target: e.target,
                    data: { edgeType: "etymology" },
                };
            });
        }

        graph = new window.G6.Graph({
            container: container,
            width: container.clientWidth,
            height: container.clientHeight,
            autoFit: "view",

            data: { nodes: g6Nodes, edges: g6Edges },

            node: {
                type: "rect",
                style: {
                    size: [110, 36],
                    fill: function (d) {
                        return d.data?.color || "#A0A0B8";
                    },
                    stroke: "transparent",
                    lineWidth: 0,
                    radius: 4,
                    labelText: function (d) {
                        var label = d.data?.label || d.id;
                        var lang = d.data?.lang || "";
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
                        if (d.data?.edgeType === "etymology") return "rgba(220,220,240,0.5)";
                        return "rgba(180,180,200,0.6)";
                    },
                    lineWidth: 1.5,
                    endArrow: function (d) {
                        return d.data?.edgeType === "etymology";
                    },
                    lineDash: function (d) {
                        if (d.data?.edgeType === "phonetic") return [5, 4];
                        return [0, 0];
                    },
                },
            },

            layout: {
                type: "d3-force",
                animate: true,
                iterations: 300,
                preventOverlap: true,
                nodeSize: 50,
                link: {
                    distance: 250,
                },
                charge: {
                    strength: -500,
                    distanceMax: 800,
                },
                collide: {
                    radius: 50,
                    strength: 0.8,
                },
            },

            behaviors: [
                "drag-canvas",
                "drag-element-force",
                "scroll-canvas",
            ],
        });

        await graph.render();

        // Pinch-to-zoom on macOS trackpads
        container.addEventListener("wheel", _wheelHandler, { passive: false });

        // Node click: show detail panel
        graph.on("node:click", function (event) {
            var nodeId = event.target.id;
            var info = nodeDataMap[nodeId];
            if (info) {
                showDetail(info.word, info.lang);
                showViewInEtymologyButton(info.word, info.lang);
            }
            graph.focusElement(nodeId, { duration: 400, easing: "ease-in-out" });
        });

        // Canvas click: hide detail panel
        graph.on("canvas:click", function () {
            var panel = document.getElementById("detail-panel");
            if (panel) panel.hidden = true;
        });
    }

    function _wheelHandler(e) {
        if (!e.ctrlKey) return;
        e.preventDefault();
        if (!graph) return;
        var zoom = graph.getZoom();
        var factor = 1 - e.deltaY * 0.01;
        var newZoom = Math.max(0.1, Math.min(5, zoom * factor));
        graph.zoomTo(newZoom, { duration: 0 });
    }

    function addPhoneticEdges(phoneticEdges) {
        if (!graph) return;
        // Rebuild full edge set and re-render
        var showEtym = document.getElementById("show-etymology-edges");
        var includeEtym = showEtym && showEtym.checked;
        _setEdges(phoneticEdges, includeEtym);
    }

    function updateEdges(phoneticEdges, etymologyEdges) {
        if (!graph) return;
        var includeEtym = etymologyEdges && etymologyEdges.length > 0;
        _setEdges(phoneticEdges, includeEtym, etymologyEdges);
    }

    function _setEdges(phoneticEdges, includeEtym, etymEdges) {
        if (!graph) return;

        var g6Edges = [];

        // Phonetic edges
        for (var i = 0; i < phoneticEdges.length; i++) {
            var pe = phoneticEdges[i];
            g6Edges.push({
                id: "p-" + pe.source + "-" + pe.target,
                source: pe.source,
                target: pe.target,
                data: { edgeType: "phonetic" },
            });
        }

        // Etymology edges
        if (includeEtym && etymEdges) {
            for (var j = 0; j < etymEdges.length; j++) {
                var ee = etymEdges[j];
                g6Edges.push({
                    id: "e-" + ee.source + "-" + ee.target,
                    source: ee.source,
                    target: ee.target,
                    data: { edgeType: "etymology" },
                });
            }
        }

        // Remove current edges, add new ones, redraw without layout
        try {
            var currentEdges = graph.getEdgeData();
            if (currentEdges && currentEdges.length > 0) {
                graph.removeData("edge", currentEdges.map(function (e) { return e.id; }));
            }
            if (g6Edges.length > 0) {
                graph.addData("edge", g6Edges);
            }
            graph.draw();
        } catch (_) {
            // Fallback: full rebuild with nodes (setData) + draw (no layout re-run)
            var g6Nodes = _allNodes.map(function (n) {
                var info = nodeDataMap[n.id];
                return {
                    id: n.id,
                    data: {
                        label: info ? info.word : n.id,
                        lang: info ? info.lang : "",
                        color: info ? langColor(info.lang) : "#A0A0B8",
                    },
                };
            });
            graph.setData({ nodes: g6Nodes, edges: g6Edges });
            graph.draw();
        }
    }

    function destroy() {
        if (graph) {
            container.removeEventListener("wheel", _wheelHandler);
            graph.destroy();
            graph = null;
        }
        nodeDataMap = {};
        _allNodes = [];
        container.innerHTML = "";
    }

    function stopLayout() {
        if (graph) {
            try { graph.stopLayout(); } catch (_) { /* layout may already be stopped */ }
        }
    }

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
        addPhoneticEdges: addPhoneticEdges,
        updateEdges: updateEdges,
        destroy: destroy,
        stopLayout: stopLayout,
        resize: resize,
    };
}
