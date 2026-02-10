import { test, expect } from "@playwright/test";
import { waitForGraph, getNodeCount, zoomToScale } from "./helpers.js";

/**
 * E2E tests for large-graph performance optimizations (SPC-00004).
 * Tests load "water" which typically produces a large graph (200+ nodes).
 * Some tests are skipped if the graph doesn't meet size thresholds.
 */

test.describe("Large graph performance (SPC-00004)", () => {
    test.describe("R1: Straight edges for large graphs", () => {
        test("large graph has smooth: false", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount <= 200, `Graph too small (${nodeCount} nodes)`);

            const smooth = await page.evaluate(() => {
                return window.__etymoNetwork.body.data.edges._data.size > 0
                    && window.__etymoNetwork.options.edges.smooth === false;
            });
            expect(smooth).toBe(true);
        });

        test("small graph keeps curved edges", async ({ page }) => {
            await page.goto("/?view=etymology&word=cat&lang=English&types=inh,bor,der&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount > 200, `Graph too large (${nodeCount} nodes)`);

            const smooth = await page.evaluate(() => {
                const s = window.__etymoNetwork.options.edges.smooth;
                return s && s.type === "continuous";
            });
            expect(smooth).toBe(true);
        });
    });

    test.describe("R2: Level-of-detail labels", () => {
        test("labels hidden when zoomed out past 0.4", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount <= 50, `Graph too small for LOD test (${nodeCount} nodes)`);

            await zoomToScale(page, 0.2);

            const fontColor = await page.evaluate(() => {
                return window.__etymoNetwork.options.nodes.font.color;
            });
            expect(fontColor).toBe("transparent");
        });

        test("labels visible when zoomed in past 0.4", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);

            // First zoom out to trigger LOD
            await zoomToScale(page, 0.2);
            // Then zoom back in
            await zoomToScale(page, 0.6);

            const fontColor = await page.evaluate(() => {
                return window.__etymoNetwork.options.nodes.font.color;
            });
            expect(fontColor).toBe("#fff");
        });
    });

    test.describe("R3: Zoom-based clustering", () => {
        test("nodes cluster when zoomed out past 0.25 on large graph", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount < 500, `Graph too small for clustering (${nodeCount} nodes)`);

            await zoomToScale(page, 0.15);

            const hasClusters = await page.evaluate(() => {
                const ids = window.__etymoNetwork.body.data.nodes.getIds();
                return ids.some(id => String(id).startsWith("cluster:"));
            });
            expect(hasClusters).toBe(true);
        });

        test("clusters open when zoomed in past 0.35", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount < 500, `Graph too small for clustering (${nodeCount} nodes)`);

            // Cluster first
            await zoomToScale(page, 0.15);
            // Then decluster
            await zoomToScale(page, 0.5);

            const hasClusters = await page.evaluate(() => {
                const ids = window.__etymoNetwork.body.data.nodes.getIds();
                return ids.some(id => String(id).startsWith("cluster:"));
            });
            expect(hasClusters).toBe(false);
        });
    });

    test.describe("R4: improvedLayout disabled for large graphs", () => {
        test("improvedLayout is false for large graphs", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount <= 200, `Graph too small (${nodeCount} nodes)`);

            const improved = await page.evaluate(() => {
                return window.__etymoNetwork.options.layout.improvedLayout;
            });
            expect(improved).toBe(false);
        });
    });

    test.describe("R5: Physics freezes after stabilization", () => {
        test("physics disabled after stabilization", async ({ page }) => {
            await page.goto("/?view=etymology&word=cat&lang=English&types=inh,bor,der&layout=force-directed");
            await waitForGraph(page);

            // Wait for stabilization (up to 10s)
            const frozen = await page.evaluate(() => {
                return new Promise((resolve) => {
                    if (!window.__etymoNetwork) return resolve(false);
                    // Check if already frozen
                    if (window.__etymoNetwork.physics?.options?.enabled === false) {
                        return resolve(true);
                    }
                    // Wait for stabilized event
                    const timeout = setTimeout(() => resolve(false), 10000);
                    window.__etymoNetwork.on("stabilized", () => {
                        clearTimeout(timeout);
                        // Check after a tick to let the handler run
                        setTimeout(() => {
                            resolve(window.__etymoNetwork.physics?.options?.enabled === false);
                        }, 50);
                    });
                });
            });
            expect(frozen).toBe(true);
        });
    });

    test.describe("R7: Barnes-Hut solver for very large graphs", () => {
        test("solver is barnesHut for 1000+ node graphs", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);
            const nodeCount = await getNodeCount(page);
            test.skip(nodeCount <= 1000, `Graph too small for barnesHut test (${nodeCount} nodes)`);

            const solver = await page.evaluate(() => {
                return window.__etymoNetwork.options.physics.solver;
            });
            expect(solver).toBe("barnesHut");
        });
    });

    test.describe("Interaction integrity", () => {
        test("new word search resets LOD and clusters", async ({ page }) => {
            await page.goto("/?view=etymology&word=water&lang=English&types=inh,bor,der,cog&layout=force-directed");
            await waitForGraph(page);

            // Trigger LOD
            await zoomToScale(page, 0.2);

            // Search a new word
            await page.goto("/?view=etymology&word=cat&lang=English&types=inh,bor,der&layout=force-directed");
            await waitForGraph(page);

            // LOD should be reset — labels visible
            const fontColor = await page.evaluate(() => {
                return window.__etymoNetwork.options.nodes.font.color;
            });
            // After a fresh graph load, the font color should be the default
            // (it may be the object form {color: "#fff"} or "#fff")
            const isVisible = fontColor !== "transparent";
            expect(isVisible).toBe(true);
        });
    });
});
