/* global beforeAll, describe, it, expect, process */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { resolve } from "path";

/**
 * Golden-fixture tests for the pure JS layout engine in graph.js/concept-map.js.
 *
 * These goldens are the cross-language oracle SPC-00021 Phase 1 ports against:
 * the Python layout package (backend/app/services/layout/) is checked for parity
 * against the SAME JSON files under tests/fixtures/layout/ (repo root, so both
 * pytest and vitest read identical inputs/outputs). Because floating-point trig
 * (cos/sin) can differ in its last bits across languages/runtimes, the Python
 * side should compare against these numbers with a small tolerance (the SSE
 * characterization suite later uses atol=0.5 px for the same reason) — JS-to-JS
 * comparison here uses exact equality since it's the same engine run twice.
 *
 * Inputs are synthetic rather than trimmed from tests/fixtures/wiktionary/*.json:
 * hand-built graphs are precise about which code paths they exercise (radial
 * ring assignment, the non-tree "extra" edge barycentric refinement needs to
 * account for, the disconnected-node fan, single-node/deep-chain edge cases)
 * without needing a separate trimming step, and are just as valid an oracle for
 * a line-for-line port.
 *
 * Regeneration: UPDATE_LAYOUT_GOLDENS=1 npx vitest run frontend/tests/layout-goldens.test.js
 * writes the current output as the new golden. Normal runs assert against it and
 * fail loudly if a golden file is missing (never silently regenerate).
 */

const graphSource = readFileSync(resolve(__dirname, "../public/js/graph.js"), "utf-8");
const conceptMapSource = readFileSync(resolve(__dirname, "../public/js/concept-map.js"), "utf-8");

const FIXTURES_DIR = resolve(__dirname, "../../tests/fixtures/layout");
const UPDATE = process.env.UPDATE_LAYOUT_GOLDENS === "1";

function loadModules() {
    const ids = [
        "graph", "legend-container", "detail-connections",
        "detail-uncertainty", "detail-panel", "detail-word",
        "detail-lang", "detail-pos", "detail-ipa", "detail-defs",
        "detail-etym", "detail-wikt", "close-panel", "toggle-panel",
        "zoom-word", "zoom-root", "zoom-fit", "etym-link-mode",
        "concept-graph", "concept-status",
    ];
    for (const id of ids) {
        if (!document.getElementById(id)) {
            const el = document.createElement("div");
            el.id = id;
            document.body.appendChild(el);
        }
    }
    const select = document.getElementById("etym-link-mode");
    if (select.tagName !== "SELECT") {
        select.remove();
        const sel = document.createElement("select");
        sel.id = "etym-link-mode";
        document.body.appendChild(sel);
    }
    const wikt = document.getElementById("detail-wikt");
    if (!wikt.href) wikt.href = "#";
    if (!document.getElementById("show-etymology-edges")) {
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.id = "show-etymology-edges";
        document.body.appendChild(cb);
    }

    window.vis = window.vis || { DataSet: class {}, Network: class {} };
    if (!window.localStorage) {
        const store = {};
        window.localStorage = {
            getItem: (k) => (k in store ? store[k] : null),
            setItem: (k, v) => {
                store[k] = String(v);
            },
            removeItem: (k) => delete store[k],
            clear: () => {
                for (const k of Object.keys(store)) delete store[k];
            },
        };
    }
    window.localStorage.setItem("graphLayout", "era-layered");

    // Vitest's jsdom environment only forwards a fixed allowlist of web-platform
    // globals from the real jsdom window onto the test's `window`/`global` — a
    // plain `eval(source)` leaves everything graph.js/concept-map.js declare
    // reachable only *during* that eval call, not after it returns (confirmed
    // empirically: probing immediately before eval returns finds every symbol
    // defined; probing window.* right after eval returns finds most of them
    // gone). So each source explicitly assigns what tests need onto `window`
    // as its own last statement, executed in the eval's own scope where the
    // bindings are still visible.
    eval(
        graphSource +
            `
        Object.assign(window, {
            classifyLang, getEraTier, groupNodesByTierAndFamily,
            assignFamilyClusterPositions, computeTreePositions,
            computeLinearTreePositions, applyBarycentricRefinement,
            buildVisEdges, baseGraphOptions, applyPerformanceOverrides, LAYOUTS,
        });
        `
    );
    eval(
        conceptMapSource +
            `
        Object.assign(window, { similarityToEdgeLength, buildConceptEdges });
        `
    );
}

beforeAll(() => {
    loadModules();
});

/** Compare `actual` against the named golden file, or (re)write it under UPDATE. */
function goldenOf(name, actual) {
    const path = resolve(FIXTURES_DIR, `${name}.json`);
    if (UPDATE) {
        mkdirSync(FIXTURES_DIR, { recursive: true });
        writeFileSync(path, JSON.stringify(actual, null, 2) + "\n");
        return actual;
    }
    if (!existsSync(path)) {
        throw new Error(
            `Missing golden fixture ${path} — run with UPDATE_LAYOUT_GOLDENS=1 to create it.`
        );
    }
    return JSON.parse(readFileSync(path, "utf-8"));
}

describe("computeTreePositions: radial path (etymology shape)", () => {
    it("multi-level chain with a non-tree edge and a disconnected node", () => {
        // root:PIE (level -2) -> mid:ProtoGermanic (-1) -> word:English (0)
        //   -> child1/child2:English (1) -> grandchild:English (2, via child1)
        // plus a "cog" edge child2<->grandchild crossing branches (exercises
        // applyBarycentricRefinement using ALL edges, not just the spanning
        // tree), and an orphan node with no edges at all (disconnected fan).
        const nodes = [
            { id: "root:PIE", level: -2 },
            { id: "mid:ProtoGermanic", level: -1 },
            { id: "word:English", level: 0 },
            { id: "child1:English", level: 1 },
            { id: "child2:English", level: 1 },
            { id: "grandchild:English", level: 2 },
            { id: "orphan:French", level: 0 },
        ];
        const edges = [
            { from: "mid:ProtoGermanic", to: "root:PIE", label: "inh" },
            { from: "word:English", to: "mid:ProtoGermanic", label: "inh" },
            { from: "child1:English", to: "word:English", label: "der" },
            { from: "child2:English", to: "word:English", label: "der" },
            { from: "grandchild:English", to: "child1:English", label: "der" },
            { from: "child2:English", to: "grandchild:English", label: "cog" },
        ];
        const actual = window.computeTreePositions(nodes, edges, "root:PIE");
        expect(actual).toEqual(goldenOf("radial-tree", actual));
    });

    it("single node, no edges — returns the root pinned at origin", () => {
        const nodes = [{ id: "solo:English", level: 0 }];
        const actual = window.computeTreePositions(nodes, [], "solo:English");
        expect(actual).toEqual(goldenOf("single-node", actual));
        expect(actual).toEqual({ "solo:English": { x: 0, y: 0 } });
    });

    it("deep unbranched chain (6 levels, no siblings)", () => {
        const nodes = Array.from({ length: 6 }, (_, i) => ({ id: `n${i}:English`, level: i - 2 }));
        const edges = nodes.slice(1).map((n, i) => ({ from: n.id, to: nodes[i].id, label: "inh" }));
        const actual = window.computeTreePositions(nodes, edges, "n0:English");
        expect(actual).toEqual(goldenOf("deep-chain", actual));
    });
});

describe("computeTreePositions: linear path (concept-map shape, no levels)", () => {
    it("a center node with three children, one of which has its own child", () => {
        const nodes = [
            { id: "center:English" },
            { id: "leaf1:French" },
            { id: "leaf2:German" },
            { id: "leaf3:Spanish" },
            { id: "deep:Italian" },
            { id: "iso:Latin" }, // disconnected — same fan logic applies here too
        ];
        const edges = [
            { from: "center:English", to: "leaf1:French" },
            { from: "center:English", to: "leaf2:German" },
            { from: "center:English", to: "leaf3:Spanish" },
            { from: "leaf1:French", to: "deep:Italian" },
        ];
        const actual = window.computeTreePositions(nodes, edges, "center:English");
        expect(actual).toEqual(goldenOf("linear-tree", actual));
    });
});

describe("era machinery", () => {
    it("getEraTier across representative language strings", () => {
        const languages = [
            "Proto-Indo-European", // DEEP_PROTO
            "Proto-Germanic", // generic Proto- (tier 1), not in DEEP_PROTO
            "Latin", // CLASSICAL_SPECIFIC
            "Ancient Greek", // "Ancient " prefix
            "Old English", // "Old " prefix
            "Middle English", // "Middle " prefix
            "Anglo-Norman", // exact-match alias for Middle-tier
            "Early Modern English", // "Early Modern " prefix
            "English", // default/modern
            null, // null -> default
        ];
        const actual = Object.fromEntries(
            languages.map((lang) => [String(lang), window.getEraTier(lang)])
        );
        expect(actual).toEqual(goldenOf("era-tiers", actual));
    });

    it("groupNodesByTierAndFamily + assignFamilyClusterPositions + buildExtraEdges", () => {
        const nodes = [
            { id: "a:English", language: "English" },
            { id: "b:German", language: "German" },
            { id: "c:French", language: "French" },
            { id: "d:OldEnglish1", language: "Old English" },
            { id: "e:OldEnglish2", language: "Old English" },
            { id: "f:Latin", language: "Latin" },
        ];
        const tieredGroups = window.groupNodesByTierAndFamily(nodes);
        const clusterPositions = window.assignFamilyClusterPositions(tieredGroups);
        const extraEdges = window.LAYOUTS["era-layered"].buildExtraEdges(nodes);
        const actual = { tieredGroups, clusterPositions, extraEdges };
        expect(actual).toEqual(goldenOf("era-grouping", actual));
    });
});

describe("classifyLang — JS/Python parity lock", () => {
    it("covers every distinct language used across these goldens, plus wide family coverage", () => {
        const languages = [
            "English", "German", "French", "Spanish", "Italian", "Latin",
            "Old English", "Middle English", "Anglo-Norman", "Early Modern English",
            "Proto-Indo-European", "Proto-Germanic", "Ancient Greek", "Greek",
            "Russian", "Sanskrit", "Arabic", "Finnish", "Turkish", "Mandarin",
            "Welsh", "Georgian", "Armenian", "Albanian", "SomeUnknownLanguage",
        ];
        const actual = Object.fromEntries(
            languages.map((lang) => [lang, window.classifyLang(lang)])
        );
        expect(actual).toEqual(goldenOf("classify-lang", actual));
    });
});

describe("per-edge physics params", () => {
    it("buildVisEdges: degree-based length/springConstant", () => {
        // A hub node (word:English) with several edges of mixed type/degree.
        const edges = [
            { from: "root:PIE", to: "mid:ProtoGermanic", label: "inh" },
            { from: "mid:ProtoGermanic", to: "word:English", label: "inh" },
            { from: "child1:English", to: "word:English", label: "der" },
            { from: "child2:English", to: "word:English", label: "der" },
            { from: "cognate:German", to: "word:English", label: "cog" },
            { from: "mention:Latin", to: "word:English", label: "mention" },
        ];
        const actual = window.buildVisEdges(edges);
        expect(actual).toEqual(goldenOf("edge-params", actual));
    });

    it("similarityToEdgeLength across the similarity range", () => {
        const inputs = [0, 0.3, 0.5, 0.75, 1.0];
        const actual = Object.fromEntries(
            inputs.map((s) => [String(s), window.similarityToEdgeLength(s)])
        );
        expect(actual).toEqual(goldenOf("similarity-to-edge-length", actual));
    });

    it("buildConceptEdges: phonetic + etymology edges, degree-aware", () => {
        const phoneticEdges = [
            { source: "fire:English", target: "feuer:German", similarity: 0.82, turchin_match: false },
            { source: "fire:English", target: "ignis:Latin", similarity: 0.35, turchin_match: true },
        ];
        const etymEdges = [
            { source: "fire:English", target: "feuer:German", relationship: "cognate" },
        ];
        const showEtym = document.getElementById("show-etymology-edges");
        showEtym.checked = true;
        const actual = window.buildConceptEdges(phoneticEdges, etymEdges);
        expect(actual).toEqual(goldenOf("concept-edges", actual));
    });
});
