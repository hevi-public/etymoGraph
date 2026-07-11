/* global beforeAll, describe, it, expect */
import { readFileSync } from "fs";
import { resolve } from "path";

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
    // Stub localStorage: newer jsdom/Vitest combinations don't forward jsdom's
    // window.localStorage onto the test global at all (it's not in Vitest's
    // hardcoded key-forwarding allowlist), so provide a minimal in-memory one.
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
    if (!window.localStorage.getItem("graphLayout")) {
        window.localStorage.setItem("graphLayout", "era-layered");
    }

    // Vitest's jsdom environment only forwards a fixed allowlist of web-platform
    // globals onto the test's window/global — a plain eval(source) leaves
    // graph.js's declarations reachable only *during* the eval call, not after
    // it returns (some symbols happen to survive, others silently don't). So
    // the evaluated source explicitly assigns what these tests need onto
    // window as its own last statement, in the eval's own scope.
    eval(
        graphSource +
            `
        Object.assign(window, {
            classifyLang, LAYOUTS, baseGraphOptions, applyPerformanceOverrides,
            LOD_SCALE_THRESHOLD, CLUSTER_THRESHOLD, DECLUSTER_THRESHOLD, CLUSTER_MIN_NODES,
            updateGraph,
        });
        `
    );
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

describe("createZoomIdleScheduler", () => {
    function makeFakeTimers() {
        let nextId = 1;
        const pending = new Map();
        return {
            setTimer: (fn, ms) => {
                const id = nextId++;
                pending.set(id, { fn, ms });
                return id;
            },
            clearTimer: (id) => pending.delete(id),
            fireAll: () => {
                for (const [id, t] of [...pending]) {
                    pending.delete(id);
                    t.fn();
                }
            },
            count: () => pending.size,
            delays: () => [...pending.values()].map((t) => t.ms),
        };
    }

    it("defaults to the ZOOM_IDLE_MS delay", () => {
        const timers = makeFakeTimers();
        const sched = window.createZoomIdleScheduler(() => {}, timers);
        sched.poke(0.5);
        expect(timers.delays()).toEqual([window.ZOOM_IDLE_MS]);
    });

    it("debounces: repeated pokes keep a single pending timer", () => {
        const timers = makeFakeTimers();
        const sched = window.createZoomIdleScheduler(() => {}, timers);
        sched.poke(0.5);
        sched.poke(0.4);
        sched.poke(0.3);
        expect(timers.count()).toBe(1);
    });

    it("fires onIdle once with the last poked scale", () => {
        const timers = makeFakeTimers();
        const calls = [];
        const sched = window.createZoomIdleScheduler((s) => calls.push(s), timers);
        sched.poke(0.5);
        sched.poke(0.2);
        timers.fireAll();
        expect(calls).toEqual([0.2]);
        expect(sched.isPending()).toBe(false);
    });

    it("cancel prevents the pending fire", () => {
        const timers = makeFakeTimers();
        const calls = [];
        const sched = window.createZoomIdleScheduler((s) => calls.push(s), timers);
        sched.poke(0.5);
        sched.cancel();
        timers.fireAll();
        expect(calls).toEqual([]);
        expect(sched.isPending()).toBe(false);
    });

    it("reschedules on poke after a fire", () => {
        const timers = makeFakeTimers();
        const calls = [];
        const sched = window.createZoomIdleScheduler((s) => calls.push(s), timers);
        sched.poke(0.5);
        timers.fireAll();
        sched.poke(0.8);
        timers.fireAll();
        expect(calls).toEqual([0.5, 0.8]);
    });
});

describe("handleZoomLOD edge-label suppression", () => {
    // Transparent-only labels still pay full per-frame text layout/draw cost;
    // LOD must zero the edge font size so the work is actually skipped
    // (node labels stay color-only — box geometry derives from label size).
    function installVisRecorder() {
        const setOptionsCalls = [];
        class DataSet {
            constructor(arr) { this._d = arr || []; this.length = this._d.length; }
            forEach(fn) { this._d.forEach(fn); }
            get() { return this._d; }
            getIds() { return this._d.map((x) => x.id); }
            update() {}
            add() {}
            clear() {}
        }
        class Network {
            constructor() {}
            on() {}
            moveTo() {}
            getPositions() { return {}; }
            setOptions(o) { setOptionsCalls.push(o); }
            destroy() {}
            isCluster() { return false; }
        }
        window.vis = { DataSet, Network };
        return setOptionsCalls;
    }

    const DATA = {
        nodes: [{ id: "water:English", label: "water", language: "English", level: 0 }],
        edges: [],
    };

    it("zooming out past the threshold zeroes edge font size", () => {
        const calls = installVisRecorder();
        window.updateGraph(DATA, { serverMode: true });
        calls.length = 0;
        window.handleZoomLOD(0.2);
        expect(calls).toEqual([{
            nodes: { font: { color: "transparent" } },
            edges: { font: { color: "transparent", size: 0 } },
        }]);
    });

    it("zooming back in restores the base edge font size", () => {
        const calls = installVisRecorder();
        window.updateGraph(DATA, { serverMode: true });
        window.handleZoomLOD(0.2);
        calls.length = 0;
        window.handleZoomLOD(0.6);
        expect(calls).toEqual([{
            nodes: { font: { color: "#fff" } },
            edges: { font: { color: "#999", size: 11 } },
        }]);
    });
});

describe("updateGraph server-mode option construction (SPC-00021)", () => {
    // Capture the options handed to `new vis.Network(...)` so we can assert the
    // physics-disabled contract without a real renderer.
    function installVisCapture() {
        let captured = null;
        class DataSet {
            constructor(arr) { this._d = arr || []; this.length = this._d.length; }
            forEach(fn) { this._d.forEach(fn); }
            get() { return this._d; }
            getIds() { return this._d.map((x) => x.id); }
            update() {}
            add() {}
            clear() {}
        }
        class Network {
            constructor(_c, _data, options) { captured = options; }
            on() {}
            moveTo() {}
            getPositions() { return {}; }
            setOptions() {}
            destroy() {}
            isCluster() { return false; }
        }
        window.vis = { DataSet, Network };
        return () => captured;
    }

    const DATA = {
        nodes: [
            { id: "water:English", label: "water", language: "English", level: 0 },
            { id: "eau:French", label: "eau", language: "French", level: -1 },
        ],
        edges: [{ from: "eau:French", to: "water:English", label: "der" }],
    };

    it("disables physics at construction in server mode", () => {
        const getCaptured = installVisCapture();
        window.updateGraph(DATA, { serverMode: true });
        expect(getCaptured().physics.enabled).toBe(false);
    });

    it("leaves physics enabled in client mode", () => {
        const getCaptured = installVisCapture();
        window.updateGraph(DATA, { serverMode: false });
        // Client mode never sets enabled:false (defaults to on).
        expect(getCaptured().physics.enabled).not.toBe(false);
    });
});
