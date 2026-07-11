import { test, expect } from "@playwright/test";
import {
    waitForGraph, getNodeCount, getZoomIdleRuns, waitForZoomIdle,
} from "./helpers.js";

/**
 * Zoom/pan gesture responsiveness on large graphs.
 *
 * Regression tests for a mid-gesture freeze: the SPC-00004 R2/R3 zoom hooks
 * (LOD + family clustering) used to run synchronously inside every wheel and
 * pinch event. network.cluster()/openCluster() take 200–400 ms on 1000-node
 * graphs, so crossing the 0.25/0.35 scale thresholds froze the gesture
 * mid-flight. The hooks are now debounced to gesture idle (ZOOM_IDLE_MS) —
 * a wheel event must never block on them.
 *
 * Runs in the default (server) layout mode; graph-size skip guards keep the
 * assertions meaningful only where clustering applies.
 */

const LARGE_GRAPH_URL =
    "/?view=etymology&word=cupboard&lang=English&types=inh,bor,der,cog&layout=era-layered";

test.describe("Zoom gesture responsiveness (large graphs)", () => {
    test("wheel events stay fast while crossing cluster thresholds", async ({ page }) => {
        await page.goto(LARGE_GRAPH_URL);
        await waitForGraph(page);
        const nodeCount = await getNodeCount(page);
        test.skip(nodeCount < 500, `Graph too small for clustering (${nodeCount} nodes)`);

        const result = await page.evaluate(() => {
            const container = document.getElementById("graph");
            const net = window.__etymoNetwork;
            net.fit({ animation: false });
            const durations = [];
            // Two phases: zoom out through the 0.25 cluster threshold, then
            // back in through the 0.35 decluster threshold — the old
            // synchronous hooks froze 200–400 ms at each crossing.
            for (const deltaY of [20, -20]) {
                for (let i = 0; i < 40; i++) {
                    const t0 = performance.now();
                    container.dispatchEvent(new WheelEvent("wheel", {
                        deltaY, ctrlKey: true, cancelable: true, bubbles: true,
                    }));
                    durations.push(performance.now() - t0);
                }
            }
            return {
                maxMs: Math.max(...durations),
                endScale: net.getScale(),
            };
        });

        // Sanity: the storm really swept across both thresholds.
        expect(result.endScale).toBeGreaterThan(0.35);
        // Generous ceiling: an event is sub-ms with the hooks deferred; the
        // old synchronous clustering blew past 200 ms.
        expect(result.maxMs).toBeLessThan(50);
    });

    test("clustering is deferred to gesture idle, not dropped", async ({ page }) => {
        await page.goto(LARGE_GRAPH_URL);
        await waitForGraph(page);
        const nodeCount = await getNodeCount(page);
        test.skip(nodeCount < 500, `Graph too small for clustering (${nodeCount} nodes)`);

        const before = await getZoomIdleRuns(page);
        const midGesture = await page.evaluate(() => {
            const container = document.getElementById("graph");
            const net = window.__etymoNetwork;
            net.fit({ animation: false });
            for (let i = 0; i < 20; i++) {
                container.dispatchEvent(new WheelEvent("wheel", {
                    deltaY: 10, ctrlKey: true, cancelable: true, bubbles: true,
                }));
            }
            // Clusters live in body.nodeIndices, not in the user DataSet.
            return {
                clustered: net.body.nodeIndices.some((id) => String(id).startsWith("cluster:")),
                scale: net.getScale(),
            };
        });

        // Below the cluster threshold mid-gesture, but nothing clustered yet.
        expect(midGesture.scale).toBeLessThan(0.25);
        expect(midGesture.clustered).toBe(false);

        // After the idle debounce the deferred hooks run and clustering lands.
        await waitForZoomIdle(page, before);
        const clustered = await page.evaluate(() => {
            return window.__etymoNetwork.body.nodeIndices
                .some((id) => String(id).startsWith("cluster:"));
        });
        expect(clustered).toBe(true);
    });

    test("full redraw stays within a sane budget", async ({ page }) => {
        await page.goto(LARGE_GRAPH_URL);
        await waitForGraph(page);
        const nodeCount = await getNodeCount(page);

        const avgMs = await page.evaluate(() => {
            const net = window.__etymoNetwork;
            net.fit({ animation: false });
            const t0 = performance.now();
            for (let i = 0; i < 10; i++) net.redraw();
            return (performance.now() - t0) / 10;
        });

        // Informational for the perf record; the assertion is a generous
        // order-of-magnitude guardrail (measured ~8.5 ms at 1,028 nodes), not
        // a tight budget — redraw time is hardware-sensitive.
        console.log(`redraw avg: ${avgMs.toFixed(2)}ms at ${nodeCount} nodes`);
        expect(avgMs).toBeLessThan(100);
    });
});
