/* global beforeAll, beforeEach, describe, it, expect */
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../public/js/layout-stream.js"),
    "utf-8"
);

/**
 * layout-stream.js is an IIFE that assigns its public surface onto `window`
 * as its final statements, so a plain eval() is enough — the window property
 * assignments survive (unlike bare lexical bindings; see graph-perf harness).
 */
function loadLayoutStream() {
    if (!window.localStorage) {
        const store = {};
        window.localStorage = {
            getItem: (k) => (k in store ? store[k] : null),
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; },
            clear: () => { for (const k of Object.keys(store)) delete store[k]; },
        };
    }
    eval(source);
}

beforeAll(() => {
    loadLayoutStream();
});

describe("getLayoutMode", () => {
    beforeEach(() => {
        window.localStorage.clear();
        window.history.replaceState(null, "", "/");
    });

    it("defaults to client with no URL param and no localStorage", () => {
        expect(window.getLayoutMode()).toBe("client");
        expect(window.__layoutMode).toBe("client");
    });

    it("reads the ?layoutMode= URL param", () => {
        window.history.replaceState(null, "", "/?layoutMode=server");
        expect(window.getLayoutMode()).toBe("server");
        expect(window.__layoutMode).toBe("server");
    });

    it("URL param wins over localStorage", () => {
        window.localStorage.setItem("layoutMode", "server");
        window.history.replaceState(null, "", "/?layoutMode=client");
        expect(window.getLayoutMode()).toBe("client");
    });

    it("falls back to localStorage when no URL param", () => {
        window.localStorage.setItem("layoutMode", "server");
        expect(window.getLayoutMode()).toBe("server");
    });

    it("ignores junk values and returns the default", () => {
        window.history.replaceState(null, "", "/?layoutMode=banana");
        expect(window.getLayoutMode()).toBe("client");
    });
});

describe("interpolatePositions", () => {
    const start = { A: { x: 0, y: 0 }, B: { x: 10, y: 10 } };
    const end = { A: [10, 20], B: [20, 30] };

    it("returns start positions at t=0", () => {
        const out = window.interpolatePositions(start, end, 0);
        const a = out.find((u) => u.id === "A");
        expect(a.x).toBe(0);
        expect(a.y).toBe(0);
    });

    it("returns end positions at t=1 (mixing [x,y] and {x,y})", () => {
        const out = window.interpolatePositions(start, end, 1);
        const a = out.find((u) => u.id === "A");
        expect(a.x).toBe(10);
        expect(a.y).toBe(20);
    });

    it("linearly interpolates at t=0.5", () => {
        const out = window.interpolatePositions(start, end, 0.5);
        const b = out.find((u) => u.id === "B");
        expect(b.x).toBe(15);
        expect(b.y).toBe(20);
    });

    it("clamps t outside [0,1]", () => {
        const over = window.interpolatePositions(start, end, 2).find((u) => u.id === "A");
        expect(over.x).toBe(10);
        const under = window.interpolatePositions(start, end, -1).find((u) => u.id === "A");
        expect(under.x).toBe(0);
    });

    it("snaps a new node (absent from start) straight to its target", () => {
        const out = window.interpolatePositions({}, { C: [5, 7] }, 0);
        const c = out.find((u) => u.id === "C");
        expect(c.x).toBe(5);
        expect(c.y).toBe(7);
    });

    it("omits ids in the skip set (dragged nodes)", () => {
        const out = window.interpolatePositions(start, end, 1, null, new Set(["A"]));
        expect(out.find((u) => u.id === "A")).toBeUndefined();
        expect(out.find((u) => u.id === "B")).toBeDefined();
    });

    it("applies a non-linear easing", () => {
        const easeOut = window.__layoutStreamInternals.easeOutCubic;
        const out = window.interpolatePositions(start, end, 0.5, easeOut);
        const a = out.find((u) => u.id === "A");
        // easeOutCubic(0.5) = 0.875 → x = 0 + 10*0.875
        expect(a.x).toBeCloseTo(8.75, 5);
    });
});

describe("createPositionTween frame application", () => {
    // A manually driven clock + rAF queue so the tween is deterministic.
    function harness() {
        const updates = [];
        const ds = { update: (arr) => updates.push(arr) };
        let clock = 0;
        let queue = [];
        const now = () => clock;
        const raf = (cb) => { queue.push(cb); return queue.length; };
        const caf = () => { queue = []; };
        const flush = () => {
            const pending = queue;
            queue = [];
            pending.forEach((fn) => fn());
        };
        const setClock = (t) => { clock = t; };
        return { updates, ds, now, raf, caf, flush, setClock };
    }

    it("tweens a node from seeded start to the frame target", () => {
        const h = harness();
        let dragged = null;
        const tween = window.createPositionTween(h.ds, {
            now: h.now, raf: h.raf, caf: h.caf, getSkip: () => dragged,
        });
        tween.seedCurrent({ A: [0, 0] });
        tween.tweenTo({ A: [100, 0] }, { durationMs: 100, easing: "linear" });

        h.setClock(0); h.flush();   // first step: t=0 → (0,0)
        h.setClock(50); h.flush();  // t=0.5 → (50,0)
        h.setClock(100); h.flush(); // t=1 → (100,0), tween ends

        const last = h.updates[h.updates.length - 1];
        const a = last.find((u) => u.id === "A");
        expect(a.x).toBe(100);
        expect(tween.isRunning()).toBe(false);
    });

    it("skips a node reported as being dragged", () => {
        const h = harness();
        let dragged = new Set(["A"]);
        const tween = window.createPositionTween(h.ds, {
            now: h.now, raf: h.raf, caf: h.caf, getSkip: () => dragged,
        });
        tween.seedCurrent({ A: [0, 0], B: [0, 0] });
        tween.tweenTo({ A: [100, 0], B: [100, 0] }, { durationMs: 100 });
        h.setClock(100); h.flush();

        const last = h.updates[h.updates.length - 1];
        expect(last.find((u) => u.id === "A")).toBeUndefined();
        expect(last.find((u) => u.id === "B")).toBeDefined();
    });

    it("syncCurrent re-baselines a node so the next tween starts from there", () => {
        // Regression for the mid-drag snap-back: a dragged node's on-screen
        // position must become the tween's start, not its stale pre-drag value.
        const h = harness();
        const tween = window.createPositionTween(h.ds, { now: h.now, raf: h.raf, caf: h.caf });
        tween.seedCurrent({ A: [0, 0] });
        // User dragged A to (500, 0) — vis knows it, the tween is told via syncCurrent.
        tween.syncCurrent({ A: [500, 0] });
        tween.tweenTo({ A: [600, 0] }, { durationMs: 100, easing: "linear" });

        h.setClock(50); h.flush();  // halfway from 500 → 600 = 550, NOT from a stale 0
        const mid = h.updates[h.updates.length - 1].find((u) => u.id === "A");
        expect(mid.x).toBe(550);
    });

    it("stop() halts the loop without further updates", () => {
        const h = harness();
        const tween = window.createPositionTween(h.ds, { now: h.now, raf: h.raf, caf: h.caf });
        tween.seedCurrent({ A: [0, 0] });
        tween.tweenTo({ A: [100, 0] }, { durationMs: 100 });
        h.setClock(0); h.flush();
        const count = h.updates.length;
        tween.stop();
        h.setClock(100); h.flush();  // nothing queued → no new updates
        expect(h.updates.length).toBe(count);
        expect(tween.isRunning()).toBe(false);
    });
});

describe("easings", () => {
    it("linear is identity", () => {
        expect(window.__layoutStreamInternals.easeLinear(0.3)).toBe(0.3);
    });
    it("easeOutCubic starts fast and ends at 1", () => {
        const e = window.__layoutStreamInternals.easeOutCubic;
        expect(e(0)).toBe(0);
        expect(e(1)).toBe(1);
        expect(e(0.5)).toBeCloseTo(0.875, 5);
    });
});
