import { test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Client-physics layout perf baseline harness (SPC-00021 §5 "Perf baseline", §10).
 *
 * Measures, per word × layout, the time from vis.Network creation to the
 * `stabilized` event ("settle") and the number of long frames (> 33 ms)
 * during the settle. Three runs per combination; the median goes into the
 * §10 baseline table. The concept map is measured too, by polling
 * `physics.stabilized` (its settle spans the similarity Worker round trip
 * and the re-stabilize it triggers, so there is no single stabilized event
 * to listen for).
 *
 * A run with no `stabilized` event within the timeout reports the fraction
 * of frames that had a node riding the maxVelocity clamp: near 1 means a
 * clamp-locked oscillation, not a slow settle (the era-layered layout does
 * this: same-tier nodes on a fixed-Y band shove each other via avoidOverlap
 * forever — the SPC-00021 §11 "era-layered 1D solve can oscillate" risk,
 * live in production). Layouts run with a fixed randomSeed, so a timed-out
 * run would repeat identically — it is not re-run RUNS times.
 *
 * Deliberately NEVER runs in CI: it is a measurement harness, not a test —
 * numbers are machine-specific and the full sweep takes minutes. Opt in with:
 *
 *   LAYOUT_BASELINE=1 npx playwright test tests/e2e/layout-baseline.spec.js --workers=1
 *   (or `make bench-layout-baseline`; requires the live stack, `make run`)
 *
 * LAYOUT_BASELINE_FIXTURES=1 additionally serves `/api/etymology/{word}/tree`
 * from the captured SPC-00013 fixtures instead of the live backend. The
 * measured window (network-created → stabilized) starts after the response
 * is parsed, so this changes nothing about the metric — it pins the exact
 * graph topology and lets the client baseline run without a loaded DB.
 * Concept-map runs are skipped in fixture mode (no captured concept-map
 * responses exist; concept resolution needs the live DB).
 *
 * LAYOUT_BASELINE_MODE=server (SPC-00021 Phase 5) measures the streamed
 * server layout instead: per §10, "settled" is the `final` frame applied
 * (`window.__lastLayoutFinal` set — the same anchor, network creation, starts
 * the window) plus the fixed 300 ms terminal ease-out tween. Long frames use
 * the same > 33 ms rAF-gap counter — a gap past two 60 Hz periods means a
 * dropped frame, the observable form of the §10 "no > 16 ms main-thread
 * frames" budget. Requires the live stack (the stream solves server-side).
 * Cold vs warm: run 1 against an empty `layouts` cache is the cold solve and
 * is reported separately; runs 2+ hit the cache (`final` arrives with zero
 * frames) and report as warm. Drop the `layouts` collection before a cold
 * sweep, e.g.:
 *
 *   docker exec <mongo> mongosh etymology --eval 'db.layouts.drop()'
 *   LAYOUT_BASELINE=1 LAYOUT_BASELINE_MODE=server npx playwright test \
 *       tests/e2e/layout-baseline.spec.js --workers=1
 */

const RUNS = 3;
const LONG_FRAME_MS = 33;
const ETYMOLOGY_SETTLE_TIMEOUT_MS = Number(process.env.LAYOUT_BASELINE_TIMEOUT_MS) || 90_000;
const CONCEPT_SETTLE_TIMEOUT_MS = 120_000;
// The concept map re-stabilizes when the similarity Worker delivers edges;
// "settled" = the last stabilized transition, confirmed by this quiet period.
const CONCEPT_QUIET_MS = 2_000;
// Above this fraction of frames with a node at the maxVelocity clamp, an
// unstabilized run is a non-converging oscillation, not a slow settle.
const CLAMP_LOCK_FRACTION = 0.9;

const WORDS = ["cheese", "fire", "hound", "wine", "cupboard"];
// Both by default; LAYOUT_BASELINE_LAYOUTS narrows a rerun to one layout
// (pair with LAYOUT_BASELINE_TIMEOUT_MS for slow-settling large graphs).
const GRAPH_LAYOUTS = (process.env.LAYOUT_BASELINE_LAYOUTS || "era-layered,force-directed").split(",");
const TYPES = "inh,bor,der,cog";

const FIXTURE_MODE = !!process.env.LAYOUT_BASELINE_FIXTURES;
const FIXTURES_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "fixtures", "wiktionary");

// client (default) measures vis.js physics to `stabilized`; server measures the
// SPC-00021 streamed layout to `final`-applied + tween.
const MODE = process.env.LAYOUT_BASELINE_MODE === "server" ? "server" : "client";
// layout-stream.js's terminal ease-out tween duration — part of "settled".
const SERVER_TWEEN_MS = 300;
const SERVER_SETTLE_TIMEOUT_MS = 30_000;

/** rows accumulated across tests (single worker), printed as the §10 table in afterAll */
const results = [];

/**
 * Installed via page.addInitScript before any app script runs.
 *
 * Etymology probe: graph.js assigns `window.__etymoNetwork = network` right
 * after `new vis.Network(...)`, so an accessor property intercepts creation
 * exactly. On each assignment it stamps createdAt, listens for `stabilized`,
 * and counts long rAF frames until the settle.
 *
 * Concept probe: concept-map.js keeps its network in a top-level `let`
 * (a global *lexical* binding — it never becomes a window property), so a
 * setter cannot intercept it. Instead an rAF poller resolves the shared
 * global binding each frame, stamps createdAt on first sight, and records
 * every false→true transition of `network.physics.stabilized` (the Worker
 * round trip re-stabilizes, so the *last* transition is the real settle).
 */
function installBenchProbes({ longFrameMs, mode, serverTweenMs }) {
    // --- etymology graph probe ---
    window.__layoutBench = null;
    let currentNetwork = null;
    Object.defineProperty(window, "__etymoNetwork", {
        configurable: true,
        get() { return currentNetwork; },
        set(network) {
            currentNetwork = network;
            if (!network) return;
            const bench = {
                createdAt: performance.now(),
                stabilizedAt: null,
                finalAt: null,      // server mode: `final` frame applied
                longFrames: 0,
                frames: 0,
                clampFrames: 0, // frames where some node rides the maxVelocity clamp
            };
            window.__layoutBench = bench;
            if (mode === "server") {
                // Settle = __lastLayoutFinal set (app.js resets it per request
                // before the network exists) + the terminal tween. Long frames
                // are counted through the tween's end.
                let last = bench.createdAt;
                const tick = (now) => {
                    if (bench.finalAt !== null && now >= bench.finalAt + serverTweenMs) return;
                    bench.frames += 1;
                    if (now - last > longFrameMs) bench.longFrames += 1;
                    last = now;
                    if (bench.finalAt === null && window.__lastLayoutFinal) {
                        bench.finalAt = now;
                    }
                    requestAnimationFrame(tick);
                };
                requestAnimationFrame(tick);
                return;
            }
            network.on("stabilized", () => {
                if (bench.stabilizedAt === null) bench.stabilizedAt = performance.now();
            });
            const clampThreshold = (network.physics.options.maxVelocity || 50) - 0.1;
            let last = bench.createdAt;
            const tick = (now) => {
                if (bench.stabilizedAt !== null) return;
                bench.frames += 1;
                if (now - last > longFrameMs) bench.longFrames += 1;
                last = now;
                const velocities = network.physics.physicsBody.velocities || {};
                for (const id in velocities) {
                    const v = velocities[id];
                    if (Math.hypot(v.x, v.y) >= clampThreshold) {
                        bench.clampFrames += 1;
                        break;
                    }
                }
                requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        },
    });

    // --- concept map probe ---
    const concept = {
        createdAt: null,
        lastSettle: null,   // { t, longFrames } at the most recent false→true transition
        stabilizedNow: false,
        finalAt: null,      // server mode: `final` frame applied
        longFrames: 0,
        frames: 0,
        nodeCount: 0,
    };
    window.__conceptBench = concept;
    let conceptLast = null;
    let wasStabilized = false;
    const conceptTick = (now) => {
        let network = null;
        try {
            network = conceptNetwork;
        } catch {
            // binding not created yet (concept-map.js still loading)
        }
        if (network) {
            if (concept.createdAt === null) {
                concept.createdAt = now;
                conceptLast = now;
                wasStabilized = false;
            } else {
                // Server mode: freeze the counters once the settle (final +
                // tween) completes, like the etymology probe.
                if (mode === "server" && concept.finalAt !== null
                    && now >= concept.finalAt + serverTweenMs) {
                    return;
                }
                concept.frames += 1;
                if (now - conceptLast > longFrameMs) concept.longFrames += 1;
                conceptLast = now;
                if (mode === "server") {
                    if (concept.finalAt === null && window.__lastLayoutFinal) {
                        concept.finalAt = now;
                    }
                } else {
                    const stabilized = network.physics && network.physics.stabilized === true;
                    if (stabilized && !wasStabilized) {
                        concept.lastSettle = { t: now, longFrames: concept.longFrames };
                    }
                    wasStabilized = stabilized;
                    concept.stabilizedNow = stabilized;
                }
                concept.nodeCount = network.body.data.nodes.length;
            }
        }
        requestAnimationFrame(conceptTick);
    };
    requestAnimationFrame(conceptTick);
}

const fixtureTreeCache = new Map();

/** Captured /tree response for a fixture word, or null if not captured. */
function fixtureTree(word) {
    if (!fixtureTreeCache.has(word)) {
        let tree = null;
        try {
            const fixture = JSON.parse(readFileSync(join(FIXTURES_DIR, `${word}.json`), "utf8"));
            tree = fixture.system_output.tree_inh_bor_der_cog;
        } catch {
            // no fixture for this word — fall through to 404
        }
        fixtureTreeCache.set(word, tree);
    }
    return fixtureTreeCache.get(word);
}

/** Serve /tree from SPC-00013 captures; fail every other API call fast. */
async function routeApiFromFixtures(page) {
    await page.route("**/api/**", async (route) => {
        const url = route.request().url();
        const match = url.match(/\/api\/etymology\/([^/]+)\/tree\b/);
        if (match && url.includes(`types=${encodeURIComponent(TYPES)}`)) {
            const tree = fixtureTree(decodeURIComponent(match[1]));
            if (tree) return route.fulfill({ json: tree });
        }
        return route.fulfill({ status: 404, json: { detail: "layout-baseline fixture mode" } });
    });
}

function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * One etymology-graph run. Returns the measurement, or — when no `stabilized`
 * event arrives within the timeout — a `{ settled: false, clampFraction }`
 * diagnostic (a clampFraction near 1 means the solver is riding the
 * maxVelocity clamp: a non-converging oscillation, not a slow settle).
 */
async function measureEtymologyRun(page, word, layout) {
    await page.goto("about:blank");
    // Pin client mode explicitly: since the Phase 5 flip the app defaults to
    // server (physics disabled — `stabilized` never fires), which would burn
    // the full settle timeout on every cell and report garbage.
    await page.goto(`/?view=etymology&word=${word}&lang=English&types=${TYPES}&layout=${layout}&layoutMode=client`);
    try {
        await page.waitForFunction(
            () => window.__layoutBench && window.__layoutBench.stabilizedAt !== null,
            undefined,
            { timeout: ETYMOLOGY_SETTLE_TIMEOUT_MS }
        );
    } catch {
        return await page.evaluate(() => ({
            settled: false,
            clampFraction: window.__layoutBench && window.__layoutBench.frames > 0
                ? window.__layoutBench.clampFrames / window.__layoutBench.frames
                : null,
            nodeCount: window.__etymoNodesDS ? window.__etymoNodesDS.length : 0,
        }));
    }
    return await page.evaluate(() => ({
        settled: true,
        settleMs: window.__layoutBench.stabilizedAt - window.__layoutBench.createdAt,
        longFrames: window.__layoutBench.longFrames,
        nodeCount: window.__etymoNodesDS ? window.__etymoNodesDS.length : 0,
    }));
}

/** One concept-map run; null if it never settled within the timeout. */
async function measureConceptRun(page, word) {
    await page.goto("about:blank");
    // layoutMode=client pinned for the same reason as measureEtymologyRun.
    await page.goto(`/?view=concept&concepts=${word}&layoutMode=client`);
    try {
        await page.waitForFunction(
            (quietMs) => {
                const bench = window.__conceptBench;
                return bench && bench.lastSettle && bench.stabilizedNow
                    && performance.now() - bench.lastSettle.t > quietMs;
            },
            CONCEPT_QUIET_MS,
            { timeout: CONCEPT_SETTLE_TIMEOUT_MS }
        );
    } catch {
        return null;
    }
    return await page.evaluate(() => ({
        settled: true,
        settleMs: window.__conceptBench.lastSettle.t - window.__conceptBench.createdAt,
        longFrames: window.__conceptBench.lastSettle.longFrames,
        nodeCount: window.__conceptBench.nodeCount,
    }));
}

/**
 * One server-mode etymology run. Settle := `final` applied
 * (`window.__lastLayoutFinal` set) + the fixed terminal tween; the window
 * starts at network creation, same anchor as the client metric. On timeout,
 * reports whether the flag resolved to server and whether a `final` ever
 * arrived. Interpretation: `finalSeen=false` with `layoutMode=server` means
 * the stream never delivered a final — a slow solve OR the client fallback
 * having engaged (the flag never changes on fallback; its only writer is
 * getLayoutMode()). A `layoutMode: "client"` value could only be a stale
 * localStorage pin, never fallback detection.
 */
async function measureServerEtymologyRun(page, word, layout) {
    await page.goto("about:blank");
    await page.goto(`/?view=etymology&word=${word}&lang=English&types=${TYPES}&layout=${layout}`);
    try {
        await page.waitForFunction(
            () => window.__layoutBench && window.__layoutBench.finalAt !== null,
            undefined,
            { timeout: SERVER_SETTLE_TIMEOUT_MS }
        );
    } catch {
        return await page.evaluate(() => ({
            settled: false,
            layoutMode: window.__layoutMode ?? null,
            finalSeen: !!window.__lastLayoutFinal,
            nodeCount: window.__etymoNodesDS ? window.__etymoNodesDS.length : 0,
        }));
    }
    // Let the terminal tween finish so its frames are in the long-frame count
    // (the probe freezes the counters at finalAt + tween).
    await page.waitForTimeout(SERVER_TWEEN_MS + 100);
    return await page.evaluate((tweenMs) => ({
        settled: true,
        settleMs: (window.__layoutBench.finalAt - window.__layoutBench.createdAt) + tweenMs,
        longFrames: window.__layoutBench.longFrames,
        layoutMode: window.__layoutMode,
        nodeCount: window.__etymoNodesDS ? window.__etymoNodesDS.length : 0,
    }), SERVER_TWEEN_MS);
}

/** One server-mode concept-map run; same settle definition as the etymology run. */
async function measureServerConceptRun(page, word) {
    await page.goto("about:blank");
    await page.goto(`/?view=concept&concepts=${word}`);
    try {
        await page.waitForFunction(
            () => window.__conceptBench && window.__conceptBench.finalAt !== null,
            undefined,
            { timeout: SERVER_SETTLE_TIMEOUT_MS }
        );
    } catch {
        return await page.evaluate(() => ({
            settled: false,
            layoutMode: window.__layoutMode ?? null,
            finalSeen: !!window.__lastLayoutFinal,
            nodeCount: window.__conceptBench ? window.__conceptBench.nodeCount : 0,
        }));
    }
    await page.waitForTimeout(SERVER_TWEEN_MS + 100);
    return await page.evaluate((tweenMs) => ({
        settled: true,
        settleMs: (window.__conceptBench.finalAt - window.__conceptBench.createdAt) + tweenMs,
        longFrames: window.__conceptBench.longFrames,
        layoutMode: window.__layoutMode,
        nodeCount: window.__conceptBench.nodeCount,
    }), SERVER_TWEEN_MS);
}

/**
 * Server-mode cold/warm cell. Run 1 (empty `layouts` cache) is the cold
 * solve; runs 2+ are cache hits ("warm"). E.g.
 * "cold 1.42 s / warm 0.61 s (0/0 long frames)".
 */
function summarizeServer(runs) {
    const [cold, ...warmRuns] = runs;
    const warm = warmRuns.filter((r) => r && r.settled);
    const part = (r) => (r && r.settled ? `${(r.settleMs / 1000).toFixed(2)} s` : "did not settle");
    const warmCell = warm.length
        ? `${(median(warm.map((r) => r.settleMs)) / 1000).toFixed(2)} s`
        : "did not settle";
    const longs = `${cold && cold.settled ? cold.longFrames : "?"}/${
        warm.length ? Math.round(median(warm.map((r) => r.longFrames))) : "?"}`;
    return {
        cell: `cold ${part(cold)} / warm ${warmCell} (${longs} long frames)`,
        nodeCount: runs.find((r) => r && r.nodeCount)?.nodeCount ?? null,
    };
}

/** Median-of-runs summary cell, e.g. "2.31 s (14 long frames, 3/3 runs)". */
function summarize(runs, timeoutMs = ETYMOLOGY_SETTLE_TIMEOUT_MS) {
    const settled = runs.filter((r) => r && r.settled);
    if (settled.length === 0) {
        const timedOut = runs.find((r) => r && r.settled === false && r.clampFraction != null);
        let cell = `did not settle within ${timeoutMs / 1000} s`;
        if (timedOut) {
            const pct = Math.round(timedOut.clampFraction * 100);
            cell = timedOut.clampFraction > CLAMP_LOCK_FRACTION
                ? `never stabilizes — clamp-locked oscillation (${pct}% of frames at maxVelocity; ` +
                  "physics runs indefinitely)"
                : `did not stabilize within ${timeoutMs / 1000} s (${pct}% of frames at the velocity clamp)`;
        }
        return { cell, nodeCount: runs.find((r) => r && r.nodeCount)?.nodeCount ?? null };
    }
    const settleS = (median(settled.map((r) => r.settleMs)) / 1000).toFixed(2);
    const longFrames = Math.round(median(settled.map((r) => r.longFrames)));
    return {
        cell: `${settleS} s (${longFrames} long frames, ${settled.length}/${RUNS} runs)`,
        nodeCount: settled[0].nodeCount,
    };
}

test.describe("Layout perf baseline (SPC-00021 §5/§10)", () => {
    // Measurement harness, not a test — opt-in only, deliberately never in CI.
    test.skip(!process.env.LAYOUT_BASELINE, "opt-in perf harness: set LAYOUT_BASELINE=1 (never runs in CI)");
    // The server layout streams from the live backend; fixtures can't serve it.
    test.skip(MODE === "server" && FIXTURE_MODE,
        "LAYOUT_BASELINE_MODE=server needs the live stack; unset LAYOUT_BASELINE_FIXTURES");

    for (const word of WORDS) {
        test(`baseline: ${word}`, async ({ page }) => {
            test.setTimeout(MODE === "server"
                ? RUNS * (GRAPH_LAYOUTS.length + 1) * SERVER_SETTLE_TIMEOUT_MS + 60_000
                : RUNS * (GRAPH_LAYOUTS.length * ETYMOLOGY_SETTLE_TIMEOUT_MS + CONCEPT_SETTLE_TIMEOUT_MS) + 60_000
            );
            await page.addInitScript(installBenchProbes, {
                longFrameMs: LONG_FRAME_MS, mode: MODE, serverTweenMs: SERVER_TWEEN_MS,
            });
            if (FIXTURE_MODE) await routeApiFromFixtures(page);

            const row = { word, nodeCount: null, layouts: {}, concept: null };

            for (const layout of GRAPH_LAYOUTS) {
                const runs = [];
                for (let i = 0; i < RUNS; i++) {
                    const run = MODE === "server"
                        ? await measureServerEtymologyRun(page, word, layout)
                        : await measureEtymologyRun(page, word, layout);
                    runs.push(run);
                    console.log(`  ${word} × ${layout} run ${i + 1}/${RUNS}: ${run.settled
                        ? `${(run.settleMs / 1000).toFixed(2)} s, ${run.longFrames} long frames, ${run.nodeCount} nodes`
                        : MODE === "server"
                            ? `no final within ${SERVER_SETTLE_TIMEOUT_MS / 1000} s ` +
                              `(layoutMode=${run.layoutMode}, finalSeen=${run.finalSeen})`
                            : `no stabilized event within ${ETYMOLOGY_SETTLE_TIMEOUT_MS / 1000} s ` +
                              `(${Math.round((run.clampFraction ?? 0) * 100)}% of frames at the velocity clamp)`}`);
                    // Layouts run with a fixed randomSeed, so a timed-out run would
                    // repeat identically — re-running only burns another timeout.
                    if (!run.settled && MODE !== "server") break;
                }
                const summary = MODE === "server" ? summarizeServer(runs) : summarize(runs);
                row.layouts[layout] = summary.cell;
                row.nodeCount = row.nodeCount ?? summary.nodeCount;
            }

            if (FIXTURE_MODE) {
                row.concept = "skipped (fixture mode)";
                console.log(`  ${word} × concept-map: skipped in fixture mode (needs live DB)`);
            } else if (MODE === "server") {
                const runs = [];
                for (let i = 0; i < RUNS; i++) {
                    const run = await measureServerConceptRun(page, word);
                    runs.push(run);
                    console.log(`  ${word} × concept-map run ${i + 1}/${RUNS}: ${run.settled
                        ? `${(run.settleMs / 1000).toFixed(2)} s, ${run.longFrames} long frames, ${run.nodeCount} nodes`
                        : `no final within ${SERVER_SETTLE_TIMEOUT_MS / 1000} s ` +
                          `(layoutMode=${run.layoutMode}, finalSeen=${run.finalSeen})`}`);
                }
                row.concept = summarizeServer(runs).cell;
            } else {
                const runs = [];
                for (let i = 0; i < RUNS; i++) {
                    const run = await measureConceptRun(page, word);
                    runs.push(run);
                    console.log(`  ${word} × concept-map run ${i + 1}/${RUNS}: ${run
                        ? `${(run.settleMs / 1000).toFixed(2)} s, ${run.longFrames} long frames, ${run.nodeCount} nodes`
                        : `did not settle within ${CONCEPT_SETTLE_TIMEOUT_MS / 1000} s`}`);
                    if (!run) break; // deterministic seed — a timed-out concept run repeats identically
                }
                row.concept = summarize(runs, CONCEPT_SETTLE_TIMEOUT_MS).cell;
            }

            results.push(row);
        });
    }

    test.afterAll(() => {
        if (results.length === 0) return;
        const header = MODE === "server"
            ? `Layout baseline — server streaming (settle = final applied + ${SERVER_TWEEN_MS} ms tween), ` +
              `run 1 = cold cache, warm = median of runs 2–${RUNS}`
            : `Layout baseline — client physics, median of ${RUNS} runs`;
        const lines = [
            "",
            header + (FIXTURE_MODE ? " (trees served from SPC-00013 fixtures)" : " (live stack)"),
            "",
            "| Graph | Nodes | era-layered settle | force-directed settle | concept map settle |",
            "|---|---|---|---|---|",
        ];
        for (const row of results) {
            lines.push(`| ${row.word} | ${row.nodeCount ?? "?"} | ${row.layouts["era-layered"] ?? "not measured"} | ${
                row.layouts["force-directed"] ?? "not measured"} | ${row.concept} |`);
        }
        lines.push("");
        console.log(lines.join("\n"));
    });
});
