/* global
   getSelectedTypes, getEtymologyTree, updateGraph, LAYOUTS, currentLayout,
   searchWords, selectNodeById,
   getConceptMap, getConceptSuggestions, updateConceptMap, updateConceptEdges,
   destroyConceptMap, currentSimilarityThreshold,
   router
*/

let currentWord = "wine";
let currentLang = "English";
let activeView = "etymology"; // "etymology" | "concept"
let currentConcept = "";

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

async function selectWord(word, lang, skipRoute = false) {
    if (!lang) {
        lang = await resolveLanguage(word);
    }
    currentWord = word;
    currentLang = lang;
    try {
        const types = getSelectedTypes();
        const data = await getEtymologyTree(word, lang, types);
        if (data.nodes.length === 0) {
            data.nodes = [{ id: `${word}:${lang}`, label: word, language: lang, level: 0 }];
        }
        updateGraph(data);
        if (!skipRoute) {
            router.push({ view: "etymology", word, lang });
        }
    } catch (e) {
        console.error("Failed to load etymology:", e);
    }
}

// --- View switching ---

function switchView(view, skipRoute = false) {
    if (view === activeView) return;
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

async function loadConceptMap(concept, pos, skipRoute = false) {
    currentConcept = concept;
    try {
        const data = await getConceptMap(concept, pos || null);
        updateConceptMap(data);
        if (!skipRoute) {
            router.push({ view: "concept", concept, pos: pos || "" });
        }
    } catch (e) {
        console.error("Failed to load concept map:", e);
    }
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
            document.getElementById("concept-search-input").value = item.concept;
            list.hidden = true;
            loadConceptMap(item.concept, getSelectedPos());
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
        selectWord(currentWord, currentLang, true);
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
    selectWord(currentWord, currentLang, true);
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
        loadConceptMap(q, getSelectedPos());
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

similaritySlider.addEventListener("input", () => {
    const val = parseInt(similaritySlider.value) / 100;
    similarityValue.textContent = val.toFixed(2);
    currentSimilarityThreshold = val;
    updateConceptEdges();
    router.replace({ similarity: parseInt(similaritySlider.value) });
});

// Etymology edges checkbox
document.getElementById("show-etymology-edges").addEventListener("change", (e) => {
    updateConceptEdges();
    router.replace({ etymEdges: e.target.checked });
});

// POS filter radio
document.querySelectorAll("input[name='concept-pos']").forEach((radio) => {
    radio.addEventListener("change", () => {
        if (currentConcept) {
            const pos = getSelectedPos();
            loadConceptMap(currentConcept, pos, true);
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
    if (state.view === "concept" && state.concept) {
        document.getElementById("concept-search-input").value = state.concept;
    }
}

// Register popstate handler for back/forward
router.onNavigate((state) => {
    activeView = ""; // reset so switchView's early-return guard doesn't skip
    updateDOMFromState(state);
    switchView(state.view, true);
    if (state.view === "etymology") {
        selectWord(state.word, state.lang, true);
    } else if (state.view === "concept") {
        loadConceptMap(state.concept, state.pos, true);
    }
});

// Capture original URL before router.initialize() modifies it via replaceState.
const originalParams = new URLSearchParams(window.location.search);

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
    loadConceptMap(initial.concept, initial.pos, true);
} else {
    selectWord(initial.word, initial.lang, true);
}
