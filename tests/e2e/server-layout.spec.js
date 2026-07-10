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
        test("server is the default layout mode (Phase 5 flip)", async ({ page }) => {
            // Deliberately no ?layoutMode= param: with a fresh context (empty
            // localStorage) the default must resolve to server and stream a
            // final — the only test that would fail if the flip were reverted.
            await page.goto("/?word=cat&lang=English&types=inh,bor,der&layout=force-directed");
            await waitForGraph(page);
            expect(await page.evaluate(() => window.__layoutMode)).toBe("server");
            await waitForFinalFrame(page, 6000);
        });

        test("publishes server mode and disables physics at construction", async ({ page }) => {
            await page.goto("/?word=cat&lang=English&types=inh,bor,der&layout=force-directed&layoutMode=server");
            await waitForGraph(page);

            const mode = await page.evaluate(() => window.__layoutMode);
            expect(mode).toBe("server");

            const physicsEnabled = await page.evaluate(
                // vis-network keeps module options on network.physics.options;
                // network.options holds only locale/clickToUse.
                () => window.__etymoNetwork.physics.options.enabled
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
                window.__etymoNetwork.physics.options.enabled,
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
                window.conceptNetwork.physics.options.enabled,
                window.conceptNetwork.body.data.edges.length,
            ]);
            expect(physicsEnabled).toBe(false);
            // The `graph` event carried phonetic edges directly (no worker).
            expect(edgeCount).toBeGreaterThan(0);
        });

        test("multi-concept words render the accent-blended membership tint", async ({ page }) => {
            // The Phase 5 fix: the server `graph` event carries per-word
            // `concepts` membership, normalized onto `_concepts` and blended
            // into the node color. Asserting the RENDERED color pins the whole
            // glue chain — severing normalizeConceptMembership (or dropping the
            // color map) regresses only this test.
            await page.goto("/?view=concept&concepts=fire,water&layoutMode=server");
            await waitForConceptMap(page);
            await waitForFinalFrame(page, 15000);

            const report = await page.evaluate(() => {
                // conceptWords/conceptNodesDS/conceptColorMap are top-level
                // lexical bindings shared with the page's global scope;
                // blendHexColors/langColor are the app's own color functions.
                const tagged = conceptWords.filter((w) => w._concepts && w._concepts.length > 0);
                const w = tagged[0];
                const expected = w && blendHexColors(
                    langColor(w.lang), conceptColorMap[w._concepts[0]] || "#5B8DEF", 0.2
                );
                return {
                    total: conceptWords.length,
                    taggedCount: tagged.length,
                    actual: w ? conceptNodesDS.get(w.id).color : null,
                    expected,
                };
            });
            expect(report.total).toBeGreaterThan(0);
            expect(report.taggedCount).toBe(report.total);
            expect(report.actual).toMatch(/^rgb\(/);
            expect(report.actual).toBe(report.expected);
        });

        test("a similarity change re-solves without enabling client physics", async ({ page }) => {
            await page.goto("/?view=concept&concepts=fire&similarity=100&layoutMode=server");
            await waitForConceptMap(page);
            await waitForFinalFrame(page, 6000);

            // Lower the threshold — server mode re-requests a solve (debounced).
            await page.evaluate(() => { window.__lastLayoutFinal = null; });
            // The slider lives inside the filters popover, hidden until toggled.
            await page.click("#filters-btn");
            await page.fill("#similarity-slider", "50");
            await page.locator("#similarity-slider").dispatchEvent("input");
            await waitForFinalFrame(page, 6000);

            const physicsEnabled = await page.evaluate(
                () => window.conceptNetwork.physics.options.enabled
            );
            expect(physicsEnabled).toBe(false);
        });
    });
});
