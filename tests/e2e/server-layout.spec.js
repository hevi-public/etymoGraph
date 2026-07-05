import { test, expect } from "@playwright/test";
import { waitForGraph, waitForConceptMap, waitForFinalFrame, getNodeCount } from "./helpers.js";

/**
 * E2E for server-side layout streaming (SPC-00021 Phase 3+4), driven with
 * `?layoutMode=server`. Asserts the streaming contract at the browser altitude:
 * physics stays disabled, the `final` frame lands, and a blocked stream falls
 * back to the client physics path. Requires the full stack (`make run`) with
 * loaded data; time-to-final uses a generous CI ceiling (the real perf target
 * lives in the env-gated baseline harness, not here).
 */

test.describe("Server-side layout streaming (SPC-00021)", () => {
    test.describe("Etymology graph", () => {
        test("publishes server mode and disables physics at construction", async ({ page }) => {
            await page.goto("/?word=cat&lang=English&types=inh,bor,der&layout=force-directed&layoutMode=server");
            await waitForGraph(page);

            const mode = await page.evaluate(() => window.__layoutMode);
            expect(mode).toBe("server");

            const physicsEnabled = await page.evaluate(
                () => window.__etymoNetwork.options.physics.enabled
            );
            expect(physicsEnabled).toBe(false);
        });

        test("applies the terminal final frame to every node", async ({ page }) => {
            await page.goto("/?word=cat&lang=English&types=inh,bor,der&layout=force-directed&layoutMode=server");
            await waitForGraph(page);
            await waitForFinalFrame(page, 6000);

            const [finalCount, nodeCount] = await page.evaluate(() => [
                Object.keys(window.__lastLayoutFinal.positions).length,
                window.__etymoNodesDS.length,
            ]);
            expect(finalCount).toBe(nodeCount);
        });

        test("falls back to client physics when the stream is blocked", async ({ page }) => {
            // Abort the SSE request at the real boundary — the E2E analog of the
            // acceptance fail_next: forces the fallback path, mocks nothing.
            await page.route("**/tree/layout/stream*", (route) => route.abort());

            await page.goto("/?word=cat&lang=English&types=inh,bor,der&layout=force-directed&layoutMode=server");
            await waitForGraph(page);

            const nodeCount = await getNodeCount(page);
            expect(nodeCount).toBeGreaterThan(0);

            // Fallback renders via the client engine (physics not force-disabled)
            // and never applies a streamed final frame.
            const [physicsEnabled, finalApplied] = await page.evaluate(() => [
                window.__etymoNetwork.options.physics.enabled,
                window.__lastLayoutFinal,
            ]);
            expect(physicsEnabled).not.toBe(false);
            expect(finalApplied).toBeFalsy();
        });
    });

    test.describe("Concept map", () => {
        test("renders phonetic edges without a Web Worker and keeps physics off", async ({ page }) => {
            await page.goto("/?view=concept&concepts=fire&layoutMode=server");
            await waitForConceptMap(page);
            await waitForFinalFrame(page, 6000);

            const [physicsEnabled, edgeCount] = await page.evaluate(() => [
                window.conceptNetwork.options.physics.enabled,
                window.conceptNetwork.body.data.edges.length,
            ]);
            expect(physicsEnabled).toBe(false);
            // The `graph` event carried phonetic edges directly (no worker).
            expect(edgeCount).toBeGreaterThan(0);
        });

        test("a similarity change re-solves without enabling client physics", async ({ page }) => {
            await page.goto("/?view=concept&concepts=fire&similarity=100&layoutMode=server");
            await waitForConceptMap(page);
            await waitForFinalFrame(page, 6000);

            // Lower the threshold — server mode re-requests a solve (debounced).
            await page.evaluate(() => { window.__lastLayoutFinal = null; });
            await page.fill("#similarity-slider", "50");
            await page.locator("#similarity-slider").dispatchEvent("input");
            await waitForFinalFrame(page, 6000);

            const physicsEnabled = await page.evaluate(
                () => window.conceptNetwork.options.physics.enabled
            );
            expect(physicsEnabled).toBe(false);
        });
    });
});
