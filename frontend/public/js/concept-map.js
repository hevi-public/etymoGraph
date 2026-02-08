/**
 * Concept Map: Phonetic similarity visualization for semantic fields.
 * Sibling view to the etymology graph, sharing vis.js + language family colors.
 */

/* global vis, classifyLang, langColor, showDetail, selectWord, switchView, LANG_FAMILIES */

let conceptNetwork = null;
let conceptNodesDS = null;
let conceptEdgesDS = null;
let allPhoneticEdges = [];
let allEtymologyEdges = [];
let conceptEdgeBaseColors = {};  // id → {color, highlight} original edge colors
let conceptWords = [];
let currentSimilarityThreshold = 0.6;

const conceptContainer = document.getElementById("concept-graph");

function similarityToEdgeLength(similarity) {
    const minLength = 50;
    const maxLength = 250;
    return maxLength - (similarity * (maxLength - minLength));
}

function initConceptMap() {
    if (conceptNetwork) {
        conceptNetwork.destroy();
        conceptNetwork = null;
    }
}

function updateConceptMap(data) {
    initConceptMap();

    // Deduplicate words by ID (same word+lang may appear with different POS)
    const seenIds = new Set();
    const uniqueWords = [];
    for (const w of data.words) {
        if (!seenIds.has(w.id)) {
            seenIds.add(w.id);
            uniqueWords.push(w);
        }
    }

    conceptWords = uniqueWords;
    allPhoneticEdges = data.phonetic_edges;
    allEtymologyEdges = data.etymology_edges || [];

    // Build nodes
    const visNodes = uniqueWords.map((w) => {
        const color = langColor(w.lang);
        const label = `${w.word}\n(${w.lang})`;
        return {
            id: w.id,
            label,
            color,
            shape: "box",
            font: { size: 13, multi: true, color: "#fff" },
            margin: 10,
            borderWidth: 0,
            title: `${w.word} (${w.lang})\nIPA: ${w.ipa || "—"}\nDolgo: ${w.dolgo_consonants || "—"}`,
        };
    });

    // Filter phonetic edges by current threshold
    const filteredEdges = filterPhoneticEdges(allPhoneticEdges, currentSimilarityThreshold);
    const visEdges = buildConceptEdges(filteredEdges, allEtymologyEdges);

    conceptNodesDS = new vis.DataSet(visNodes);
    conceptEdgesDS = new vis.DataSet(visEdges);

    // Store base edge colors for highlight reset
    conceptEdgeBaseColors = {};
    conceptEdgesDS.forEach((e) => {
        conceptEdgeBaseColors[e.id] = {
            color: e.color?.color || "#555",
            highlight: e.color?.highlight || "#aaa",
        };
    });

    const options = {
        layout: {
            randomSeed: 42,
            improvedLayout: true,
        },
        edges: {
            color: { color: "#555", highlight: "#aaa" },
            font: { color: "#999", size: 10, strokeWidth: 0 },
            smooth: { type: "continuous" },
        },
        nodes: {
            shape: "box",
            borderWidth: 0,
            font: { size: 13, multi: true, color: "#fff" },
            margin: 10,
        },
        physics: {
            solver: "barnesHut",
            barnesHut: {
                gravitationalConstant: -8000,
                centralGravity: 0.08,
                springLength: 250,
                springConstant: 0.005,
                damping: 0.5,
                avoidOverlap: 0.5,
            },
            stabilization: false,
            minVelocity: 0.75,
            maxVelocity: 30,
        },
        interaction: {
            zoomView: false,
            dragView: true,
            hover: true,
        },
    };

    conceptNetwork = new vis.Network(
        conceptContainer,
        { nodes: conceptNodesDS, edges: conceptEdgesDS },
        options
    );

    conceptNetwork.on("click", (params) => {
        if (params.nodes.length > 0) {
            const clickedId = params.nodes[0];
            const w = conceptWords.find((n) => n.id === clickedId);
            if (w) {
                showDetail(w.word, w.lang);
                showViewInEtymologyButton(w.word, w.lang);
            }
            highlightConnected(clickedId);
            const pos = conceptNetwork.getPositions([clickedId])[clickedId];
            if (pos) {
                conceptNetwork.moveTo({
                    position: { x: pos.x, y: pos.y },
                    animation: { duration: 400, easingFunction: "easeInOutQuad" },
                });
            }
        } else {
            resetConceptHighlight();
        }
    });

    // Trackpad: pinch zoom + pan
    conceptContainer.addEventListener("wheel", handleConceptWheel, { passive: false });
}

function handleConceptWheel(e) {
    if (!conceptNetwork) return;
    e.preventDefault();
    if (e.ctrlKey) {
        const scale = conceptNetwork.getScale();
        const newScale = scale * (1 - e.deltaY * 0.01);
        conceptNetwork.moveTo({ scale: Math.max(0.1, Math.min(5, newScale)), animation: false });
    } else {
        const pos = conceptNetwork.getViewPosition();
        const scale = conceptNetwork.getScale();
        conceptNetwork.moveTo({
            position: { x: pos.x + e.deltaX / scale, y: pos.y + e.deltaY / scale },
            animation: false,
        });
    }
}

function filterPhoneticEdges(edges, threshold) {
    return edges.filter((e) => e.similarity >= threshold || e.turchin_match);
}

function buildConceptEdges(phoneticEdges, etymEdges) {
    // Compute degree (number of connections) per node across all edge types
    const degree = {};
    const showEtym = document.getElementById("show-etymology-edges");
    const includeEtym = showEtym && showEtym.checked;
    for (const e of phoneticEdges) {
        degree[e.source] = (degree[e.source] || 0) + 1;
        degree[e.target] = (degree[e.target] || 0) + 1;
    }
    if (includeEtym) {
        for (const e of etymEdges) {
            degree[e.source] = (degree[e.source] || 0) + 1;
            degree[e.target] = (degree[e.target] || 0) + 1;
        }
    }

    const BASE_SPRING = 0.008;
    const visEdges = [];

    // Phonetic similarity edges: dashed grey
    for (const e of phoneticEdges) {
        const opacity = Math.max(0.2, e.similarity);
        const width = 0.35 + 1.5 * e.similarity;
        const dFrom = degree[e.source] || 1;
        const dTo = degree[e.target] || 1;
        const combined = dFrom + dTo;
        const maxDeg = Math.max(dFrom, dTo);
        const baseLength = similarityToEdgeLength(e.similarity);
        visEdges.push({
            from: e.source,
            to: e.target,
            dashes: [5, 5],
            color: { color: `rgba(180,180,200,${opacity})`, highlight: `rgba(200,200,220,${opacity + 0.2})` },
            width,
            length: baseLength + 40 * Math.log2(1 + combined),
            springConstant: BASE_SPRING / Math.log2(1 + maxDeg),
            title: `${(e.similarity * 100).toFixed(0)}% similar${e.turchin_match ? " (Turchin match)" : ""}`,
            edgeType: "phonetic",
        });
    }

    // Etymology edges: solid dark with arrows
    if (includeEtym) {
        for (const e of etymEdges) {
            const dFrom = degree[e.source] || 1;
            const dTo = degree[e.target] || 1;
            const combined = dFrom + dTo;
            const maxDeg = Math.max(dFrom, dTo);
            visEdges.push({
                from: e.source,
                to: e.target,
                dashes: false,
                color: { color: "rgba(220,220,240,0.5)", highlight: "rgba(255,255,255,0.7)" },
                width: 1,
                arrows: "to",
                length: 120 + 40 * Math.log2(1 + combined),
                springConstant: BASE_SPRING / Math.log2(1 + maxDeg),
                title: e.relationship || "etymological",
                edgeType: "etymology",
            });
        }
    }

    return visEdges;
}

function updateConceptEdges() {
    if (!conceptEdgesDS) return;
    const filtered = filterPhoneticEdges(allPhoneticEdges, currentSimilarityThreshold);
    const visEdges = buildConceptEdges(filtered, allEtymologyEdges);
    conceptEdgesDS.clear();
    conceptEdgesDS.add(visEdges);

    // Refresh base edge colors after rebuild
    conceptEdgeBaseColors = {};
    conceptEdgesDS.forEach((e) => {
        conceptEdgeBaseColors[e.id] = {
            color: e.color?.color || "#555",
            highlight: e.color?.highlight || "#aaa",
        };
    });
}

function applyRgbaOpacity(rgbaStr, factor) {
    const match = rgbaStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (match) {
        const baseAlpha = match[4] !== undefined ? parseFloat(match[4]) : 1;
        return `rgba(${match[1]},${match[2]},${match[3]},${(baseAlpha * factor).toFixed(2)})`;
    }
    // Hex fallback
    if (rgbaStr.startsWith("#")) {
        const r = parseInt(rgbaStr.slice(1, 3), 16);
        const g = parseInt(rgbaStr.slice(3, 5), 16);
        const b = parseInt(rgbaStr.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${factor.toFixed(2)})`;
    }
    return rgbaStr;
}

function highlightConnected(nodeId) {
    if (!conceptNodesDS || !conceptEdgesDS) return;
    const connectedEdges = conceptEdgesDS.get({
        filter: (e) => e.from === nodeId || e.to === nodeId,
    });
    const connectedNodeIds = new Set([nodeId]);
    const connectedEdgeIds = new Set();
    for (const e of connectedEdges) {
        connectedNodeIds.add(e.from);
        connectedNodeIds.add(e.to);
        connectedEdgeIds.add(e.id);
    }

    const updates = [];
    conceptNodesDS.forEach((n) => {
        const connected = connectedNodeIds.has(n.id);
        const baseColor = langColor(conceptWords.find((w) => w.id === n.id)?.lang || "");
        updates.push({
            id: n.id,
            color: connected ? baseColor : "rgba(100,100,120,0.2)",
            font: { color: connected ? "#fff" : "rgba(255,255,255,0.2)" },
        });
    });
    conceptNodesDS.update(updates);

    // Dim non-connected edges
    const edgeUpdates = [];
    conceptEdgesDS.forEach((e) => {
        const connected = connectedEdgeIds.has(e.id);
        const base = conceptEdgeBaseColors[e.id] || { color: "#555", highlight: "#aaa" };
        if (connected) {
            edgeUpdates.push({ id: e.id, color: { color: base.color, highlight: base.highlight } });
        } else {
            edgeUpdates.push({
                id: e.id,
                color: {
                    color: applyRgbaOpacity(base.color, 0.15),
                    highlight: applyRgbaOpacity(base.highlight, 0.15),
                },
            });
        }
    });
    conceptEdgesDS.update(edgeUpdates);
}

function resetConceptHighlight() {
    if (!conceptNodesDS) return;
    const updates = [];
    conceptNodesDS.forEach((n) => {
        const w = conceptWords.find((w) => w.id === n.id);
        updates.push({
            id: n.id,
            color: langColor(w?.lang || ""),
            font: { color: "#fff" },
        });
    });
    conceptNodesDS.update(updates);

    // Restore edges to base colors
    if (conceptEdgesDS) {
        const edgeUpdates = [];
        for (const id in conceptEdgeBaseColors) {
            const base = conceptEdgeBaseColors[id];
            edgeUpdates.push({ id, color: { color: base.color, highlight: base.highlight } });
        }
        conceptEdgesDS.update(edgeUpdates);
    }
}

function showViewInEtymologyButton(word, lang) {
    let btn = document.getElementById("view-in-etymology-btn");
    if (!btn) {
        btn = document.createElement("button");
        btn.id = "view-in-etymology-btn";
        btn.className = "view-etymology-btn";
        btn.textContent = "View in Etymology Graph";
        const connectionsDiv = document.getElementById("detail-connections");
        connectionsDiv.parentNode.insertBefore(btn, connectionsDiv);
    }
    btn.hidden = false;
    btn.onclick = (e) => {
        e.preventDefault();
        // Switch to etymology view and load this word
        if (typeof switchView === "function") {
            switchView("etymology");
            selectWord(word, lang);
        }
    };
}

function destroyConceptMap() {
    if (conceptNetwork) {
        conceptNetwork.destroy();
        conceptNetwork = null;
    }
    conceptNodesDS = null;
    conceptEdgesDS = null;
    allPhoneticEdges = [];
    allEtymologyEdges = [];
    conceptWords = [];
    conceptEdgeBaseColors = {};
}
