/* global
   getSelectedTypes, getEtymologyTree, updateGraph, LAYOUTS, currentLayout,
   searchWords, selectNodeById,
   getConceptMap, getConceptSuggestions, updateConceptMap, updateConceptEdges,
   destroyConceptMap, currentSimilarityThreshold,
   router,
   getLayoutMode, openLayoutStream, closeLayoutStream, applyLayoutFrame,
   applyConceptLayoutFrame, buildEtymologyLayoutStreamURL, buildConceptLayoutStreamURL
*/

let currentWord = "wine";
let currentLang = "English";
let currentEtym = null;
let activeView = "etymology"; // "etymology" | "concept"

// Multi-concept state
let activeConcepts = []; // [{concept, accentColor}]
const CONCEPT_ACCENT_COLORS = [
    "#5B8DEF", "#EF5B5B", "#43D9A2", "#F5C842",
    "#CE6BF0", "#FF8C42", "#00BCD4", "#8BC34A",
];

// --- Etymology view functions ---

function getSelectedTypes() {
    const checkboxes = document.querySelectorAll("#ety-filters input[type=checkbox]:checked");
    const types = Array.from(checkboxes).map((cb) => cb.value);
    return types.length > 0 ? types.join(",") : "inh";
}

async function resolveLanguage(word) {
    try {
        const data = await searchWords(word);
        const exact = data.results.find((r) => r.word.toLowerCase() === word.toLowerCase());
        return exact ? exact.lang : (data.results[0] ? data.results[0].lang : "English");
    } catch (_) {
        return "English";
    }
}

async function selectWord(word, lang, skipRoute = false, etym = null) {
    if (!lang) {
        lang = await resolveLanguage(word);
    }
    currentWord = word;
    currentLang = lang;
    currentEtym = etym;
    const types = getSelectedTypes();

    // Server mode (SPC-00021): one SSE request streams graph → frames → final.
    if (getLayoutMode() === "server") {
        loadEtymologyServer(word, lang, types, etym);
        if (!skipRoute) {
            router.push({ view: "etymology", word, lang, etym: etym || "" });
        }
        return;
    }

    try {
        const data = await getEtymologyTree(word, lang, types, etym);
        if (data.nodes.length === 0) {
            data.nodes = [{ id: `${word}:${lang}`, label: word, language: lang, level: 0 }];
        }
        updateGraph(data);
        if (!skipRoute) {
            router.push({ view: "etymology", word, lang, etym: etym || "" });
        }
    } catch (e) {
        console.error("Failed to load etymology:", e);
    }
}

/** Ensure a non-empty node set so an unknown word still renders one orphan node. */
function ensureOrphanNode(nodes, word, lang) {
    return (nodes && nodes.length)
        ? nodes
        : [{ id: `${word}:${lang}`, label: word, language: lang, level: 0 }];
}

/**
 * Server-mode etymology load: open the layout stream, build the graph from the
 * first `graph` event (physics off), tween each frame, and settle on `final`.
 * Any stream error or first-graph timeout falls back to today's client path.
 */
function loadEtymologyServer(word, lang, types, etym) {
    const url = buildEtymologyLayoutStreamURL(word, lang, types, currentLayout, etym);
    window.__lastLayoutFinal = null;  // reset the E2E "final applied" hook per request
    openLayoutStream(url, {
        onGraph: (g) => {
            updateGraph(
                { nodes: ensureOrphanNode(g.nodes, word, lang), edges: g.edges || [] },
                { serverMode: true }
            );
        },
        onFrame: (f) => applyLayoutFrame(f.positions, { final: false }),
        onFinal: (f) => {
            applyLayoutFrame(f.positions, { final: true });
            window.__lastLayoutFinal = f;
        },
        onError: () => loadEtymologyClientFallback(word, lang, types, etym),
    });
}

/** Fallback: today's exact client path (fetch /tree + client physics). */
async function loadEtymologyClientFallback(word, lang, types, etym) {
    try {
        const data = await getEtymologyTree(word, lang, types, etym);
        data.nodes = ensureOrphanNode(data.nodes, word, lang);
        updateGraph(data, { serverMode: false });
    } catch (e) {
        console.error("Failed to load etymology (fallback):", e);
    }
}

// --- View switching ---

function switchView(view, skipRoute = false) {
    if (view === activeView) return;
    // Cancel any in-flight layout stream from the view we're leaving, and any
    // pending debounced concept re-solve — if that timer fired after the
    // switch it would reopen a concept stream and silently close the new
    // view's in-flight stream (the singleton close raises no error event, so
    // no fallback would run).
    if (typeof closeLayoutStream === "function") closeLayoutStream();
    clearTimeout(similarityResolveTimer);
    activeView = view;

    const etymControls = document.getElementById("etymology-controls");
    const conceptControls = document.getElementById("concept-controls");
    const graphDiv = document.getElementById("graph");
    const conceptGraphDiv = document.getElementById("concept-graph");

    // Update toggle buttons
    document.querySelectorAll(".view-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.view === view);
    });

    // Toggle filter groups inside popover
    document.getElementById("ety-filters").hidden = view !== "etymology";
    document.getElementById("concept-filters").hidden = view !== "concept";

    if (view === "etymology") {
        etymControls.hidden = false;
        conceptControls.hidden = true;
        graphDiv.hidden = false;
        conceptGraphDiv.hidden = true;
        destroyConceptMap();
        removeConceptLegend();
        // Hide "View in Etymology Graph" button if present
        const etymBtn = document.getElementById("view-in-etymology-btn");
        if (etymBtn) etymBtn.hidden = true;
    } else {
        etymControls.hidden = true;
        conceptControls.hidden = false;
        graphDiv.hidden = true;
        conceptGraphDiv.hidden = false;
        document.getElementById("detail-panel").hidden = true;
    }

    if (!skipRoute) {
        router.push({ view });
    }
}

// --- Concept map functions ---

let conceptDebounceTimer = null;

function nextAccentColor() {
    const used = new Set(activeConcepts.map((c) => c.accentColor));
    const unused = CONCEPT_ACCENT_COLORS.find((c) => !used.has(c));
    return unused || CONCEPT_ACCENT_COLORS[activeConcepts.length % CONCEPT_ACCENT_COLORS.length];
}

function addConcept(concept, skipRoute = false) {
    if (activeConcepts.some((c) => c.concept === concept)) return;
    activeConcepts.push({ concept, accentColor: nextAccentColor() });
    renderChips();
    reloadConceptMap(skipRoute);
}

function removeConcept(concept) {
    activeConcepts = activeConcepts.filter((c) => c.concept !== concept);
    renderChips();
    if (activeConcepts.length === 0) {
        destroyConceptMap();
        removeConceptLegend();
        router.replace({ concepts: "" });
    } else {
        reloadConceptMap();
    }
}

function renderChips() {
    const container = document.getElementById("concept-chips");
    container.innerHTML = "";
    for (const c of activeConcepts) {
        const chip = document.createElement("span");
        chip.className = "concept-chip";
        chip.style.setProperty("--chip-color", c.accentColor);

        const dot = document.createElement("span");
        dot.className = "chip-dot";
        chip.appendChild(dot);

        chip.appendChild(document.createTextNode(c.concept));

        const btn = document.createElement("button");
        btn.className = "chip-remove";
        btn.type = "button";
        btn.textContent = "\u00d7";
        btn.addEventListener("click", () => removeConcept(c.concept));
        chip.appendChild(btn);

        container.appendChild(chip);
    }
}

function buildConceptColorMap() {
    const map = {};
    for (const c of activeConcepts) {
        map[c.concept] = c.accentColor;
    }
    return map;
}

/** Merge per-concept API results: dedupe words by id (tagging membership),
 *  dedupe etymology edges by endpoint pair. Mirrors the server-side merge. */
function mergeConceptResults(results) {
    const mergedWords = new Map();
    const mergedEtymEdges = [];
    const seenEdges = new Set();
    for (let i = 0; i < results.length; i++) {
        const data = results[i];
        const conceptName = activeConcepts[i].concept;
        for (const w of data.words) {
            if (mergedWords.has(w.id)) {
                mergedWords.get(w.id)._concepts.push(conceptName);
            } else {
                mergedWords.set(w.id, { ...w, _concepts: [conceptName] });
            }
        }
        for (const e of (data.etymology_edges || [])) {
            const key = [e.source, e.target].sort().join("|");
            if (!seenEdges.has(key)) {
                seenEdges.add(key);
                mergedEtymEdges.push(e);
            }
        }
    }
    return {
        words: Array.from(mergedWords.values()),
        etymology_edges: mergedEtymEdges,
        _conceptColorMap: buildConceptColorMap(),
    };
}

async function reloadConceptMap(skipRoute = false) {
    if (activeConcepts.length === 0) return;
    const pos = getSelectedPos();

    // Server mode (SPC-00021): one SSE request handles the multi-concept merge,
    // phonetic edges, and solve. The legend/route are the same in both modes.
    if (getLayoutMode() === "server") {
        loadConceptServer(pos);
        updateConceptLegend();
        if (!skipRoute) {
            router.push({
                view: "concept",
                concepts: activeConcepts.map((c) => c.concept).join(","),
                pos: pos || "",
            });
        }
        return;
    }

    try {
        const results = await Promise.all(
            activeConcepts.map((c) => getConceptMap(c.concept, pos || null))
        );
        updateConceptMap(mergeConceptResults(results));
        updateConceptLegend();
        if (!skipRoute) {
            router.push({
                view: "concept",
                concepts: activeConcepts.map((c) => c.concept).join(","),
                pos: pos || "",
            });
        }
    } catch (e) {
        console.error("Failed to load concept map:", e);
    }
}

/**
 * Server-mode concept load: stream `/concept-map/layout` for the joined concept
 * list at the current threshold/pos/etym-edges. The `graph` event carries the
 * merged words + precomputed phonetic edges; frames tween in. Errors fall back
 * to the per-concept client merge + worker path.
 */
function loadConceptServer(pos) {
    const concepts = activeConcepts.map((c) => c.concept).join(",");
    const includeEtym = document.getElementById("show-etymology-edges").checked;
    const url = buildConceptLayoutStreamURL(concepts, {
        pos: pos || null,
        threshold: currentSimilarityThreshold,
        includeEtymologyEdges: includeEtym,
    });
    window.__lastLayoutFinal = null;  // reset the E2E "final applied" hook per request
    openLayoutStream(url, {
        onGraph: (g) => {
            updateConceptMap({
                words: g.words || [],
                etymology_edges: g.etymology_edges || [],
                phonetic_edges: g.phonetic_edges || [],
                clusters: g.clusters || [],
                _conceptColorMap: buildConceptColorMap(),
            }, { serverMode: true });
        },
        onFrame: (f) => applyConceptLayoutFrame(f.positions, { final: false }),
        onFinal: (f) => {
            applyConceptLayoutFrame(f.positions, { final: true });
            window.__lastLayoutFinal = f;
        },
        onError: () => loadConceptClientFallback(pos),
    });
}

/** Fallback: today's exact per-concept client merge + Web Worker path. */
async function loadConceptClientFallback(pos) {
    try {
        const results = await Promise.all(
            activeConcepts.map((c) => getConceptMap(c.concept, pos || null))
        );
        updateConceptMap(mergeConceptResults(results), { serverMode: false });
        updateConceptLegend();
    } catch (e) {
        console.error("Failed to load concept map (fallback):", e);
    }
}

function updateConceptLegend() {
    removeConceptLegend();
    if (activeConcepts.length < 2) return;
    const legend = document.createElement("div");
    legend.className = "concept-legend";
    legend.id = "concept-legend";
    for (const c of activeConcepts) {
        const item = document.createElement("div");
        item.className = "concept-legend-item";
        const dot = document.createElement("span");
        dot.className = "concept-legend-dot";
        dot.style.background = c.accentColor;
        item.appendChild(dot);
        item.appendChild(document.createTextNode(c.concept));
        legend.appendChild(item);
    }
    document.getElementById("graph-wrapper").appendChild(legend);
}

function removeConceptLegend() {
    const existing = document.getElementById("concept-legend");
    if (existing) existing.remove();
}

function renderConceptSuggestions(matches) {
    const list = document.getElementById("concept-suggestions");
    list.innerHTML = "";
    if (matches.length === 0) {
        list.hidden = true;
        return;
    }
    matches.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item.concept + " ";
        const countSpan = document.createElement("span");
        countSpan.className = "lang-hint";
        countSpan.textContent = `${item.translation_count} languages`;
        li.appendChild(countSpan);
        li.addEventListener("click", () => {
            document.getElementById("concept-search-input").value = "";
            list.hidden = true;
            addConcept(item.concept);
        });
        list.appendChild(li);
    });
    list.hidden = false;
}

function getSelectedPos() {
    const checked = document.querySelector("input[name='concept-pos']:checked");
    return checked ? checked.value : "";
}

// --- Wire up controls ---

// View toggle buttons
document.querySelectorAll(".view-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.dataset.view));
});

// Filters popover toggle
const filtersBtn = document.getElementById("filters-btn");
const filtersPopover = document.getElementById("filters-popover");

filtersBtn.addEventListener("click", () => {
    filtersPopover.hidden = !filtersPopover.hidden;
});

document.addEventListener("click", (e) => {
    if (!e.target.closest("#filters-btn") && !e.target.closest("#filters-popover")) {
        filtersPopover.hidden = true;
    }
});

// Re-fetch etymology when connection filter changes
document.getElementById("ety-filters").addEventListener("change", (e) => {
    if (e.target.matches("input[type=checkbox]")) {
        selectWord(currentWord, currentLang, true, currentEtym);
        router.replace({ types: getSelectedTypes() });
    }
});

// Layout selector: populate from LAYOUTS registry and wire change handler
const layoutSelect = document.getElementById("layout-select");
for (const [key, layout] of Object.entries(LAYOUTS)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = layout.label;
    layoutSelect.appendChild(opt);
}
layoutSelect.value = currentLayout;

layoutSelect.addEventListener("change", () => {
    currentLayout = layoutSelect.value;
    localStorage.setItem("graphLayout", currentLayout);
    selectWord(currentWord, currentLang, true, currentEtym);
    router.replace({ layout: layoutSelect.value });
});

// --- Concept search autocomplete ---

const conceptSearchInput = document.getElementById("concept-search-input");
const conceptSuggestions = document.getElementById("concept-suggestions");
const conceptClearBtn = document.getElementById("concept-clear-btn");

conceptSearchInput.addEventListener("input", () => {
    const q = conceptSearchInput.value.trim();
    conceptClearBtn.hidden = q === "";
    if (q === "") {
        conceptSuggestions.hidden = true;
        return;
    }
    clearTimeout(conceptDebounceTimer);
    conceptDebounceTimer = setTimeout(async () => {
        try {
            const data = await getConceptSuggestions(q);
            renderConceptSuggestions(data.suggestions);
        } catch (e) {
            conceptSuggestions.hidden = true;
        }
    }, 300);
});

conceptSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        const q = conceptSearchInput.value.trim();
        if (!q) return;
        conceptSuggestions.hidden = true;
        clearTimeout(conceptDebounceTimer);
        addConcept(q);
        conceptSearchInput.value = "";
        conceptClearBtn.hidden = true;
    }
});

conceptClearBtn.addEventListener("click", () => {
    conceptSearchInput.value = "";
    conceptClearBtn.hidden = true;
    conceptSuggestions.hidden = true;
    conceptSearchInput.focus();
});

document.addEventListener("click", (e) => {
    if (!e.target.closest("#concept-controls .search-container")) {
        conceptSuggestions.hidden = true;
    }
});

// Similarity slider
const similaritySlider = document.getElementById("similarity-slider");
const similarityValue = document.getElementById("similarity-value");

let similarityResolveTimer = null;
similaritySlider.addEventListener("input", () => {
    const val = parseInt(similaritySlider.value) / 100;
    similarityValue.textContent = val.toFixed(2);
    currentSimilarityThreshold = val;
    // Both modes filter the displayed edges instantly. Server mode additionally
    // re-solves on the backend, debounced ~300 ms so a slider drag doesn't spam
    // requests; the streamed frames then tween from the current positions.
    updateConceptEdges();
    router.replace({ similarity: parseInt(similaritySlider.value) });
    if (getLayoutMode() === "server" && activeConcepts.length > 0) {
        clearTimeout(similarityResolveTimer);
        similarityResolveTimer = setTimeout(() => reloadConceptMap(true), 300);
    }
});

// Etymology edges checkbox
document.getElementById("show-etymology-edges").addEventListener("change", (e) => {
    router.replace({ etymEdges: e.target.checked });
    // Toggling etym edges changes the solve inputs, so server mode re-solves;
    // client mode just swaps the displayed edge set.
    if (getLayoutMode() === "server" && activeConcepts.length > 0) {
        reloadConceptMap(true);
    } else {
        updateConceptEdges();
    }
});

// POS filter radio
document.querySelectorAll("input[name='concept-pos']").forEach((radio) => {
    radio.addEventListener("change", () => {
        if (activeConcepts.length > 0) {
            const pos = getSelectedPos();
            reloadConceptMap(true);
            router.replace({ pos });
        }
    });
});

// --- URL-driven state restore ---

function updateDOMFromState(state) {
    // Connection type checkboxes
    const typeSet = new Set((state.types || "inh,bor,der").split(","));
    document.querySelectorAll("#ety-filters input[type=checkbox]").forEach((cb) => {
        cb.checked = typeSet.has(cb.value);
    });

    // Layout dropdown + global
    document.getElementById("layout-select").value = state.layout || "era-layered";
    currentLayout = state.layout || "era-layered";

    // Similarity slider + display + global
    const sim = state.similarity != null ? state.similarity : 100;
    document.getElementById("similarity-slider").value = sim;
    document.getElementById("similarity-value").textContent = (sim / 100).toFixed(2);
    currentSimilarityThreshold = sim / 100;

    // POS radio buttons
    const posRadio = document.querySelector(
        `input[name="concept-pos"][value="${state.pos || ""}"]`
    );
    if (posRadio) posRadio.checked = true;

    // Etymology edges checkbox
    document.getElementById("show-etymology-edges").checked =
        state.etymEdges != null ? state.etymEdges : true;

    // Search input values
    if (state.view === "etymology" && state.word) {
        document.getElementById("search-input").value = state.word;
    }

    // Restore multi-concept chips from URL state
    if (state.view === "concept" && state.concepts) {
        const conceptNames = state.concepts.split(",").filter(Boolean);
        activeConcepts = conceptNames.map((name, i) => ({
            concept: name,
            accentColor: CONCEPT_ACCENT_COLORS[i % CONCEPT_ACCENT_COLORS.length],
        }));
        renderChips();
    } else if (state.view === "concept") {
        activeConcepts = [];
        renderChips();
    }
}

// Register popstate handler for back/forward
router.onNavigate((state) => {
    activeView = ""; // reset so switchView's early-return guard doesn't skip
    updateDOMFromState(state);
    switchView(state.view, true);
    if (state.view === "etymology") {
        selectWord(state.word, state.lang, true, state.etym || null);
    } else if (state.view === "concept" && activeConcepts.length > 0) {
        reloadConceptMap(true);
    }
});

// Capture original URL before router.initialize() modifies it via replaceState.
const originalParams = new URLSearchParams(window.location.search);

// The layout mode flag is not a view-scoped router param, so persist an explicit
// ?layoutMode= into localStorage before the router normalizes the URL away.
// getLayoutMode() then reads it (URL > localStorage > "server") and publishes
// window.__layoutMode for E2E.
const urlLayoutMode = originalParams.get("layoutMode");
if (urlLayoutMode === "server" || urlLayoutMode === "client") {
    try { localStorage.setItem("layoutMode", urlLayoutMode); } catch { /* private mode */ }
}
getLayoutMode();

// Initialize router (parses URL, normalizes, attaches popstate listener)
router.initialize();

// If the original URL didn't explicitly set layout, respect localStorage preference (set by graph.js).
const initial = router.state();
if (!originalParams.has("layout")) {
    initial.layout = currentLayout;
}
router.replace(initial);
updateDOMFromState(initial);
if (initial.view === "concept") {
    switchView("concept", true);
    if (activeConcepts.length > 0) {
        reloadConceptMap(true);
    }
} else {
    selectWord(initial.word, initial.lang, true, initial.etym || null);
}
