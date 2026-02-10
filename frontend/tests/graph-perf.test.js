/* global beforeAll, describe, it, expect */
import { readFileSync } from "fs";
import { resolve } from "path";

const graphCommonSource = readFileSync(
    resolve(__dirname, "../public/js/graph-common.js"),
    "utf-8"
);
const graphSource = readFileSync(
    resolve(__dirname, "../public/js/graph.js"),
    "utf-8"
);

/**
 * Set up DOM elements that graph.js references on load,
 * then eval the source to populate the global scope with functions.
 */
function loadGraph() {
    // graph.js touches these elements at load time
    const ids = [
        "graph", "legend-container", "detail-connections",
        "detail-uncertainty", "detail-panel", "detail-word",
        "detail-lang", "detail-pos", "detail-ipa", "detail-defs",
        "detail-etym", "detail-wikt", "close-panel", "toggle-panel",
        "zoom-word", "zoom-root", "zoom-fit", "etym-link-mode",
    ];
    for (const id of ids) {
        if (!document.getElementById(id)) {
            const el = document.createElement("div");
            el.id = id;
            document.body.appendChild(el);
        }
    }
    // etym-link-mode needs to be a <select> with a .value
    const select = document.getElementById("etym-link-mode");
    if (select.tagName !== "SELECT") {
        select.remove();
        const sel = document.createElement("select");
        sel.id = "etym-link-mode";
        document.body.appendChild(sel);
    }
    // detail-wikt needs href property
    const wikt = document.getElementById("detail-wikt");
    if (!wikt.href) wikt.href = "#";

    // Stub vis global (graph.js doesn't use it at load time, but just in case)
    window.vis = window.vis || { DataSet: class {}, Network: class {} };
    // Stub localStorage
    if (!window.localStorage.getItem("graphLayout")) {
        window.localStorage.setItem("graphLayout", "era-layered");
    }

    // Combine into single eval so both files share one scope
    // (mimics browser where all <script> tags run at global scope)
    eval(graphCommonSource + "\n" + graphSource);
}

beforeAll(() => {
    loadGraph();
});

describe("applyPerformanceOverrides", () => {
    function makeOptions() {
        return {
            edges: { smooth: { type: "continuous" } },
            layout: { improvedLayout: true },
            physics: { solver: "forceAtlas2Based", forceAtlas2Based: {} },
        };
    }

    it("does not modify options for small graphs (<= 200 nodes)", () => {
        const opts = makeOptions();
        window.applyPerformanceOverrides(opts, 50);
        expect(opts.edges.smooth).toEqual({ type: "continuous" });
        expect(opts.layout.improvedLayout).toBe(true);
        expect(opts.physics.solver).toBe("forceAtlas2Based");
    });

    it("does not modify options at exactly 200 nodes", () => {
        const opts = makeOptions();
        window.applyPerformanceOverrides(opts, 200);
        expect(opts.edges.smooth).toEqual({ type: "continuous" });
        expect(opts.layout.improvedLayout).toBe(true);
    });

    it("sets straight edges and disables improvedLayout for > 200 nodes", () => {
        const opts = makeOptions();
        window.applyPerformanceOverrides(opts, 201);
        expect(opts.edges.smooth).toBe(false);
        expect(opts.layout.improvedLayout).toBe(false);
        expect(opts.physics.solver).toBe("forceAtlas2Based");
    });

    it("switches to barnesHut solver for > 1000 nodes", () => {
        const opts = makeOptions();
        window.applyPerformanceOverrides(opts, 1001);
        expect(opts.edges.smooth).toBe(false);
        expect(opts.layout.improvedLayout).toBe(false);
        expect(opts.physics.solver).toBe("barnesHut");
        expect(opts.physics.barnesHut).toEqual({ theta: 0.8 });
    });

    it("does not switch to barnesHut at exactly 1000 nodes", () => {
        const opts = makeOptions();
        window.applyPerformanceOverrides(opts, 1000);
        expect(opts.physics.solver).toBe("forceAtlas2Based");
    });
});

describe("performance threshold constants", () => {
    it("LOD threshold is 0.4", () => {
        expect(window.LOD_SCALE_THRESHOLD).toBe(0.4);
    });

    it("cluster threshold is 0.25 with decluster at 0.35 (hysteresis gap)", () => {
        expect(window.CLUSTER_THRESHOLD).toBe(0.25);
        expect(window.DECLUSTER_THRESHOLD).toBe(0.35);
        expect(window.DECLUSTER_THRESHOLD - window.CLUSTER_THRESHOLD).toBeCloseTo(0.1);
    });

    it("cluster minimum is 500 nodes", () => {
        expect(window.CLUSTER_MIN_NODES).toBe(500);
    });
});

describe("classifyLang stores family on vis nodes", () => {
    it("classifyLang returns family and color for known languages", () => {
        const result = window.classifyLang("English");
        expect(result.family).toBe("germanic");
        expect(result.color).toBe("#5B8DEF");
    });

    it("classifyLang returns 'other' for unknown languages", () => {
        const result = window.classifyLang("SomeUnknownLanguage");
        expect(result.family).toBe("other");
    });

    it("force-directed buildVisNodes includes family property", () => {
        const layout = window.LAYOUTS["force-directed"];
        const nodes = [
            { id: "water:English", label: "water", language: "English", level: 0 },
            { id: "eau:French", label: "eau", language: "French", level: -1 },
        ];
        const { visNodes } = layout.buildVisNodes(nodes, "eau:French");
        expect(visNodes[0].family).toBe("germanic");
        expect(visNodes[1].family).toBe("romance");
    });

    it("era-layered buildVisNodes includes family property", () => {
        const layout = window.LAYOUTS["era-layered"];
        const nodes = [
            { id: "water:English", label: "water", language: "English", level: 0 },
            { id: "hudor:Ancient Greek", label: "hudor", language: "Ancient Greek", level: -2 },
        ];
        const { visNodes } = layout.buildVisNodes(nodes, "hudor:Ancient Greek");
        expect(visNodes[0].family).toBe("germanic");
        expect(visNodes[1].family).toBe("greek");
    });
});

describe("baseGraphOptions convergence tuning (R6)", () => {
    it("includes minVelocity and maxVelocity in physics config", () => {
        const opts = window.baseGraphOptions({});
        expect(opts.physics.minVelocity).toBe(2.0);
        expect(opts.physics.maxVelocity).toBe(50);
    });
});
