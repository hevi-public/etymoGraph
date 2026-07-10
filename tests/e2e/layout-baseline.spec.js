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
function installBenchProbes(longFrameMs) {
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
                longFrames: 0,
                frames: 0,
                clampFrames: 0, // frames where some node rides the maxVelocity clamp
            };
            window.__layoutBench = bench;
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
                concept.frames += 1;
                if (now - conceptLast > longFrameMs) concept.longFrames += 1;
                conceptLast = now;
                const stabilized = network.physics && network.physics.stabilized === true;
                if (stabilized && !wasStabilized) {
                    concept.lastSettle = { t: now, longFrames: concept.longFrames };
                }
                wasStabilized = stabilized;
                concept.stabilizedNow = stabilized;
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
    await page.goto(`/?view=etymology&word=${word}&lang=English&types=${TYPES}&layout=${layout}`);
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
    await page.goto(`/?view=concept&concepts=${word}`);
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

    for (const word of WORDS) {
        test(`baseline: ${word}`, async ({ page }) => {
            test.setTimeout(
                RUNS * (GRAPH_LAYOUTS.length * ETYMOLOGY_SETTLE_TIMEOUT_MS + CONCEPT_SETTLE_TIMEOUT_MS) + 60_000
            );
            await page.addInitScript(installBenchProbes, LONG_FRAME_MS);
            if (FIXTURE_MODE) await routeApiFromFixtures(page);

            const row = { word, nodeCount: null, layouts: {}, concept: null };

            for (const layout of GRAPH_LAYOUTS) {
                const runs = [];
                for (let i = 0; i < RUNS; i++) {
                    const run = await measureEtymologyRun(page, word, layout);
                    runs.push(run);
                    console.log(`  ${word} × ${layout} run ${i + 1}/${RUNS}: ${run.settled
                        ? `${(run.settleMs / 1000).toFixed(2)} s, ${run.longFrames} long frames, ${run.nodeCount} nodes`
                        : `no stabilized event within ${ETYMOLOGY_SETTLE_TIMEOUT_MS / 1000} s ` +
                          `(${Math.round((run.clampFraction ?? 0) * 100)}% of frames at the velocity clamp)`}`);
                    // Layouts run with a fixed randomSeed, so a timed-out run would
                    // repeat identically — re-running only burns another timeout.
                    if (!run.settled) break;
                }
                const summary = summarize(runs);
                row.layouts[layout] = summary.cell;
                row.nodeCount = row.nodeCount ?? summary.nodeCount;
            }

            if (FIXTURE_MODE) {
                row.concept = "skipped (fixture mode)";
                console.log(`  ${word} × concept-map: skipped in fixture mode (needs live DB)`);
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
        const lines = [
            "",
            `Layout baseline — client physics, median of ${RUNS} runs` +
                (FIXTURE_MODE ? " (trees served from SPC-00013 fixtures)" : " (live stack)"),
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
