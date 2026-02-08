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
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
                gravitationalConstant: -30,
                centralGravity: 0.005,
                springLength: 150,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 0.5,
            },
            stabilization: {
                iterations: 300,
                updateInterval: 25,
            },
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
    const visEdges = [];

    // Phonetic similarity edges: dashed grey
    for (const e of phoneticEdges) {
        const opacity = Math.max(0.2, e.similarity);
        const width = 1 + 2 * e.similarity;
        visEdges.push({
            from: e.source,
            to: e.target,
            dashes: [5, 5],
            color: { color: `rgba(180,180,200,${opacity})`, highlight: `rgba(200,200,220,${opacity + 0.2})` },
            width,
            length: similarityToEdgeLength(e.similarity),
            title: `${(e.similarity * 100).toFixed(0)}% similar${e.turchin_match ? " (Turchin match)" : ""}`,
            edgeType: "phonetic",
        });
    }

    // Etymology edges: solid dark with arrows
    const showEtym = document.getElementById("show-etymology-edges");
    if (showEtym && showEtym.checked) {
        for (const e of etymEdges) {
            visEdges.push({
                from: e.source,
                to: e.target,
                dashes: false,
                color: { color: "rgba(220,220,240,0.5)", highlight: "rgba(255,255,255,0.7)" },
                width: 2,
                arrows: "to",
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
}

function highlightConnected(nodeId) {
    if (!conceptNodesDS || !conceptEdgesDS) return;
    const connectedEdges = conceptEdgesDS.get({
        filter: (e) => e.from === nodeId || e.to === nodeId,
    });
    const connectedNodeIds = new Set([nodeId]);
    for (const e of connectedEdges) {
        connectedNodeIds.add(e.from);
        connectedNodeIds.add(e.to);
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
}
