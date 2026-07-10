/**
 * Concept Map: Phonetic similarity visualization for semantic fields.
 * Sibling view to the etymology graph, sharing vis.js + language family colors.
 */

/* global vis, classifyLang, langColor, showDetail, selectWord, switchView, LANG_FAMILIES,
   computeTreePositions, getTouchDistance, getTouchCenter,
   getLayoutMode, createPositionTween, closeLayoutStream */

let conceptNetwork = null;
let conceptNodesDS = null;
let conceptEdgesDS = null;
let allPhoneticEdges = [];
let allEtymologyEdges = [];
let conceptEdgeBaseColors = {};  // id → {color, highlight} original edge colors
let conceptWords = [];
let conceptColorMap = {};  // concept name → accent color
let currentSimilarityThreshold = 1.0;
let conceptLodActive = false;
let similarityWorker = null;

// --- Server-side layout streaming (SPC-00021 Phase 3+4) ---
let conceptLayoutTween = null;         // active tween handle (server mode)
const conceptDraggingIds = new Set();  // nodes the user currently owns

const CONCEPT_LOD_THRESHOLD = 0.4;

function blendHexColors(baseHex, accentHex, ratio) {
    const parse = (hex) => [
        parseInt(hex.slice(1, 3), 16),
        parseInt(hex.slice(3, 5), 16),
        parseInt(hex.slice(5, 7), 16),
    ];
    const b = parse(baseHex);
    const a = parse(accentHex);
    const r = b.map((v, i) => Math.round(v * (1 - ratio) + a[i] * ratio));
    return `rgb(${r[0]},${r[1]},${r[2]})`;
}

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
        window.conceptNetwork = null;
    }
}

function updateConceptMap(data, opts) {
    opts = opts || {};
    // Server mode (SPC-00021): phonetic edges arrive precomputed in the `graph`
    // SSE event (no Web Worker), positions stream in and are tweened, and the
    // barnesHut solver stays disabled. `opts.serverMode` lets the fallback path
    // force the client (worker + physics) path even when the flag says "server".
    const serverMode = opts.serverMode !== undefined
        ? opts.serverMode
        : (typeof getLayoutMode === "function" && getLayoutMode() === "server");

    // Capture the outgoing positions so a threshold/etym re-solve (same word set)
    // morphs from where nodes already are instead of restarting from the seed.
    let priorPositions = null;
    if (serverMode && conceptNetwork) {
        try { priorPositions = conceptNetwork.getPositions(); } catch { priorPositions = null; }
    }

    initConceptMap();
    if (conceptLayoutTween) { conceptLayoutTween.stop(); conceptLayoutTween = null; }
    conceptDraggingIds.clear();

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
    conceptColorMap = data._conceptColorMap || {};
    // Client mode fills phonetic edges from the Web Worker; server mode receives
    // them precomputed (all pairs ≥ the display floor) in the `graph` event.
    allPhoneticEdges = serverMode ? (data.phonetic_edges || []) : [];
    allEtymologyEdges = data.etymology_edges || [];

    const hasMultipleConcepts = Object.keys(conceptColorMap).length > 1;

    // Build nodes
    const visNodes = uniqueWords.map((w) => {
        const baseColor = langColor(w.lang);
        const label = `${w.word}\n(${w.lang})`;
        // Tint background toward concept accent when multiple concepts loaded
        let color = baseColor;
        if (hasMultipleConcepts && w._concepts && w._concepts.length > 0) {
            const accent = conceptColorMap[w._concepts[0]] || "#5B8DEF";
            color = blendHexColors(baseColor, accent, 0.2);
        }
        return {
            id: w.id,
            label,
            color,
            shape: "box",
            font: { size: 13, multi: true, color: "#fff" },
            margin: 10,
            borderWidth: 0,
            title: `${w.word} (${w.lang})\nIPA: ${w.ipa || "—"}`
                + `\nDolgo: ${w.dolgo_consonants || "—"}`
                + (w._concepts?.length > 1
                    ? `\nConcepts: ${w._concepts.join(", ")}` : ""),
        };
    });

    // Client mode renders etymology edges first (phonetic arrive from the
    // worker); server mode already has phonetic edges, so render them filtered
    // to the current threshold.
    const initialPhonetic = serverMode
        ? filterPhoneticEdges(allPhoneticEdges, currentSimilarityThreshold)
        : [];
    const visEdges = buildConceptEdges(initialPhonetic, allEtymologyEdges);

    // Tree-based initial positioning: pick highest-degree node as center
    if (visEdges.length > 0) {
        const degree = {};
        for (const e of visEdges) {
            degree[e.from] = (degree[e.from] || 0) + 1;
            degree[e.to] = (degree[e.to] || 0) + 1;
        }
        const centerId = Object.entries(degree)
            .reduce((best, [id, d]) => d > best[1] ? [id, d] : best, ["", 0])[0];
        if (centerId) {
            const positions = computeTreePositions(visNodes, visEdges, centerId);
            // Center around (0,0) and scale down so physics expands rather than contracts
            const allPos = Object.values(positions);
            const cx = allPos.reduce((s, p) => s + p.x, 0) / allPos.length;
            const cy = allPos.reduce((s, p) => s + p.y, 0) / allPos.length;
            const scale = 0.3;
            for (const vn of visNodes) {
                const pos = positions[vn.id];
                if (pos) { vn.x = (pos.x - cx) * scale; vn.y = (pos.y - cy) * scale; }
            }
        }
    }

    // Server-mode continuity: surviving nodes keep their previous coordinates.
    if (serverMode && priorPositions) {
        for (const vn of visNodes) {
            const prev = priorPositions[vn.id];
            if (prev) { vn.x = prev.x; vn.y = prev.y; }
        }
    }

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
            font: { size: 13, multi: true, color: "#fff" },
            margin: 10,
        },
        physics: {
            enabled: !serverMode,
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
            maxVelocity: 50,
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

    // Expose network instance for E2E tests (top-level `let` is not a window property)
    window.conceptNetwork = conceptNetwork;

    // Server mode: tween streamed frames; keep physics off (a threshold change
    // re-solves on the backend rather than running the client barnesHut engine).
    if (serverMode && typeof createPositionTween === "function") {
        conceptLayoutTween = createPositionTween(conceptNodesDS, {
            getSkip: () => conceptDraggingIds,
        });
        try { conceptLayoutTween.seedCurrent(conceptNetwork.getPositions()); } catch { /* fresh */ }
        conceptNetwork.on("dragStart", (params) => {
            if (params?.nodes) params.nodes.forEach((id) => conceptDraggingIds.add(id));
        });
        conceptNetwork.on("dragEnd", (params) => {
            if (params?.nodes) {
                // Re-sync the tween baseline to the dropped position (see graph.js).
                if (conceptLayoutTween) {
                    conceptLayoutTween.syncCurrent(conceptNetwork.getPositions(params.nodes));
                }
                params.nodes.forEach((id) => conceptDraggingIds.delete(id));
            }
        });
    }

    // Show word count status
    const statusEl = document.getElementById("concept-status");
    if (statusEl) {
        const conceptCount = Object.keys(conceptColorMap).length;
        statusEl.textContent = conceptCount > 1
            ? `${uniqueWords.length} words across ${conceptCount} concepts`
            : `${uniqueWords.length} words with pronunciation data`;
        statusEl.hidden = false;
    }

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

    // Touch: pinch-to-zoom for tablets
    let conceptTouchState = null;

    conceptContainer.addEventListener("touchstart", (e) => {
        if (!conceptNetwork || e.touches.length !== 2) return;
        e.preventDefault();
        conceptTouchState = {
            startDist: getTouchDistance(e.touches[0], e.touches[1]),
            startScale: conceptNetwork.getScale(),
            lastCenter: getTouchCenter(e.touches[0], e.touches[1]),
        };
    }, { passive: false });

    conceptContainer.addEventListener("touchmove", (e) => {
        if (!conceptNetwork || !conceptTouchState || e.touches.length !== 2) return;
        e.preventDefault();

        const center = getTouchCenter(e.touches[0], e.touches[1]);
        const oldScale = conceptNetwork.getScale();
        const oldPos = conceptNetwork.getViewPosition();

        // Compute new scale from pinch distance
        const dist = getTouchDistance(e.touches[0], e.touches[1]);
        const ratio = dist / conceptTouchState.startDist;
        const newScale = Math.max(0.1, Math.min(5, conceptTouchState.startScale * ratio));

        // Convert pinch screen center to world coords
        const rect = conceptContainer.getBoundingClientRect();
        const pinchWorld = conceptNetwork.DOMtoCanvas({
            x: center.x - rect.left,
            y: center.y - rect.top,
        });

        // Zoom toward pinch center: keep the world point under fingers fixed
        const newPos = {
            x: pinchWorld.x - (pinchWorld.x - oldPos.x) * (oldScale / newScale),
            y: pinchWorld.y - (pinchWorld.y - oldPos.y) * (oldScale / newScale),
        };

        // Add finger pan delta (convert screen px to world units at new scale)
        newPos.x += (conceptTouchState.lastCenter.x - center.x) / newScale;
        newPos.y += (conceptTouchState.lastCenter.y - center.y) / newScale;

        conceptNetwork.moveTo({ scale: newScale, position: newPos, animation: false });
        handleConceptZoomLOD(newScale);
        conceptTouchState.lastCenter = center;
    }, { passive: false });

    conceptContainer.addEventListener("touchend", (e) => {
        if (e.touches.length < 2) conceptTouchState = null;
    }, { passive: true });

    // Client mode only: spawn the Web Worker for O(n^2) phonetic similarity
    // (non-blocking). Server mode already has the edges from the `graph` event.
    if (!serverMode) {
        if (similarityWorker) similarityWorker.terminate();
        similarityWorker = new Worker("js/similarity-worker.js");
        similarityWorker.onmessage = (msg) => {
            allPhoneticEdges = msg.data.edges;
            updateConceptEdges();
            similarityWorker = null;
        };
        similarityWorker.postMessage({
            words: uniqueWords.map((w) => ({
                id: w.id,
                dolgo_consonants: w.dolgo_consonants || "",
                dolgo_first2: w.dolgo_first2 || "",
            })),
            threshold: 0.3,
        });
    }
}

/**
 * Apply a streamed concept-map layout frame in server mode by tweening node
 * positions. No-op in client mode. Called by the app's stream glue.
 * @param {Object<string, number[]>} positions id → [x, y] from an SSE frame
 * @param {{final?: boolean}} [opts] final frames settle with a longer ease-out
 */
function applyConceptLayoutFrame(positions, opts) {
    opts = opts || {};
    if (!conceptLayoutTween || !positions) return;
    if (opts.final) {
        conceptLayoutTween.tweenTo(positions, { durationMs: 300, easing: "easeOut" });
    } else {
        conceptLayoutTween.tweenTo(positions, { durationMs: 150, easing: "linear" });
    }
}

function handleConceptZoomLOD(scale) {
    if (!conceptNetwork) return;
    if (scale < CONCEPT_LOD_THRESHOLD && !conceptLodActive) {
        conceptNetwork.setOptions({
            nodes: { font: { color: "transparent" } },
            edges: { font: { color: "transparent" } },
        });
        conceptLodActive = true;
    } else if (scale >= CONCEPT_LOD_THRESHOLD && conceptLodActive) {
        conceptNetwork.setOptions({
            nodes: { font: { color: "#fff" } },
            edges: { font: { color: "#999" } },
        });
        conceptLodActive = false;
    }
}

function handleConceptWheel(e) {
    if (!conceptNetwork) return;
    e.preventDefault();
    if (e.ctrlKey) {
        const scale = conceptNetwork.getScale();
        const newScale = scale * (1 - e.deltaY * 0.01);
        const clampedScale = Math.max(0.1, Math.min(5, newScale));
        conceptNetwork.moveTo({ scale: clampedScale, animation: false });
        handleConceptZoomLOD(clampedScale);
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

    // Etymology edges: solid, color-coded by relationship type
    if (includeEtym) {
        for (const e of etymEdges) {
            const dFrom = degree[e.source] || 1;
            const dTo = degree[e.target] || 1;
            const combined = dFrom + dTo;
            const maxDeg = Math.max(dFrom, dTo);
            const isCognate = e.relationship === "cognate";
            const edgeColor = isCognate
                ? { color: "rgba(245,200,66,0.7)", highlight: "rgba(245,200,66,1)" }
                : { color: "rgba(180,180,200,0.25)", highlight: "rgba(220,220,240,0.5)" };
            visEdges.push({
                from: e.source,
                to: e.target,
                dashes: false,
                color: edgeColor,
                width: isCognate ? 2.5 : 0.8,
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

    // Client mode: re-enable physics and stabilize so the layout settles with
    // the new edge set. Server mode filters edges client-side only (instant
    // during a slider drag); a committed threshold change re-solves on the
    // backend via the slider's release handler, not the client engine.
    const serverMode = typeof getLayoutMode === "function" && getLayoutMode() === "server";
    if (conceptNetwork && !serverMode) {
        conceptNetwork.setOptions({ physics: { enabled: true } });
        conceptNetwork.stabilize(100);
    }
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

    const hasMultipleConcepts = Object.keys(conceptColorMap).length > 1;
    const updates = [];
    conceptNodesDS.forEach((n) => {
        const connected = connectedNodeIds.has(n.id);
        const w = conceptWords.find((w) => w.id === n.id);
        if (connected) {
            let nodeColor = langColor(w?.lang || "");
            if (hasMultipleConcepts && w?._concepts?.length > 0) {
                const accent = conceptColorMap[w._concepts[0]] || "#5B8DEF";
                nodeColor = blendHexColors(nodeColor, accent, 0.2);
            }
            updates.push({ id: n.id, color: nodeColor, font: { color: "#fff" } });
        } else {
            updates.push({
                id: n.id,
                color: "rgba(100,100,120,0.2)",
                font: { color: "rgba(255,255,255,0.2)" },
            });
        }
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
    const hasMultipleConcepts = Object.keys(conceptColorMap).length > 1;
    const updates = [];
    conceptNodesDS.forEach((n) => {
        const w = conceptWords.find((w) => w.id === n.id);
        let nodeColor = langColor(w?.lang || "");
        if (hasMultipleConcepts && w?._concepts?.length > 0) {
            const accent = conceptColorMap[w._concepts[0]] || "#5B8DEF";
            nodeColor = blendHexColors(nodeColor, accent, 0.2);
        }
        updates.push({ id: n.id, color: nodeColor, font: { color: "#fff" } });
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
        // Switch to etymology view and load this word (single history entry)
        if (typeof switchView === "function") {
            switchView("etymology", true);
            selectWord(word, lang);
        }
    };
}

function destroyConceptMap() {
    if (similarityWorker) {
        similarityWorker.terminate();
        similarityWorker = null;
    }
    // Tear down any in-flight server-mode layout stream + tween.
    if (typeof closeLayoutStream === "function") closeLayoutStream();
    if (conceptLayoutTween) { conceptLayoutTween.stop(); conceptLayoutTween = null; }
    conceptDraggingIds.clear();
    if (conceptNetwork) {
        conceptNetwork.destroy();
        conceptNetwork = null;
        window.conceptNetwork = null;
    }
    conceptNodesDS = null;
    conceptEdgesDS = null;
    allPhoneticEdges = [];
    allEtymologyEdges = [];
    conceptWords = [];
    conceptColorMap = {};
    conceptEdgeBaseColors = {};
    conceptLodActive = false;
    const statusEl = document.getElementById("concept-status");
    if (statusEl) statusEl.hidden = true;
}
