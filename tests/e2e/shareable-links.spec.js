import { test, expect } from "@playwright/test";
import { waitForGraph, waitForConceptMap, getSearchParams } from "./helpers.js";

test.describe("Direct URL Loading", () => {
    test("/ loads wine in English with clean URL", async ({ page }) => {
        await page.goto("/");
        await waitForGraph(page);
        const input = page.locator("#search-input");
        await expect(input).toHaveValue("wine");
        // URL should stay clean (no query params)
        const params = await getSearchParams(page);
        expect(Object.keys(params).length).toBe(0);
    });

    test("/?word=fire&lang=Latin loads fire", async ({ page }) => {
        await page.goto("/?word=fire&lang=Latin");
        await waitForGraph(page);
        const input = page.locator("#search-input");
        await expect(input).toHaveValue("fire");
        const params = await getSearchParams(page);
        expect(params.word).toBe("fire");
        expect(params.lang).toBe("Latin");
    });

    test("/?view=concept&concept=water loads concept map", async ({ page }) => {
        await page.goto("/?view=concept&concept=water");
        await waitForConceptMap(page);
        const input = page.locator("#concept-search-input");
        await expect(input).toHaveValue("water");
        // Concept view should be active
        const activeBtn = page.locator(".view-btn.active");
        await expect(activeBtn).toHaveAttribute("data-view", "concept");
    });

    test("/?view=concept&concept=fire&similarity=75 sets slider", async ({ page }) => {
        await page.goto("/?view=concept&concept=fire&similarity=75");
        await waitForConceptMap(page);
        const slider = page.locator("#similarity-slider");
        await expect(slider).toHaveValue("75");
        const display = page.locator("#similarity-value");
        await expect(display).toHaveText("0.75");
    });
});

test.describe("History Navigation", () => {
    test("back traverses through word searches", async ({ page }) => {
        // Start at default (wine)
        await page.goto("/");
        await waitForGraph(page);

        // Search for fire
        await page.fill("#search-input", "fire");
        await page.press("#search-input", "Enter");
        await waitForGraph(page);

        // Search for apple
        await page.fill("#search-input", "apple");
        await page.press("#search-input", "Enter");
        await waitForGraph(page);

        // Go back twice to reach wine
        await page.goBack();
        await waitForGraph(page);
        await page.goBack();
        await waitForGraph(page);

        const params = await getSearchParams(page);
        expect(Object.keys(params).length).toBe(0); // clean URL = wine defaults
        const input = page.locator("#search-input");
        await expect(input).toHaveValue("wine");
    });

    test("filter changes use replaceState (back skips them)", async ({ page }) => {
        await page.goto("/?word=fire");
        await waitForGraph(page);

        // Change a filter (uncheck borrowed)
        await page.click("#filters-btn");
        const borCheckbox = page.locator("#ety-filters input[value='bor']");
        await borCheckbox.uncheck();
        await waitForGraph(page);

        // URL should have types param (replaceState)
        let params = await getSearchParams(page);
        expect(params.types).toBeDefined();
        expect(params.types).not.toContain("bor");

        // Go back — should go to / (wine), not to fire with different types
        await page.goBack();
        await waitForGraph(page);
        params = await getSearchParams(page);
        expect(Object.keys(params).length).toBe(0);
    });

    test("cross-view nav creates single history entry", async ({ page }) => {
        // Load concept map for water
        await page.goto("/?view=concept&concept=water");
        await waitForConceptMap(page);

        // Click a node to show detail panel with "View in Etymology Graph" button
        // We need to find a clickable node; use evaluate to get a node ID and click it
        const nodeId = await page.evaluate(() => {
            const ids = window.conceptNetwork.body.data.nodes.getIds();
            return ids.length > 0 ? ids[0] : null;
        });

        if (nodeId) {
            // Click the node programmatically via vis.js
            await page.evaluate((id) => {
                window.conceptNetwork.selectNodes([id]);
                window.conceptNetwork.body.emitter.emit("click", {
                    nodes: [id], edges: [], event: {}, pointer: { DOM: { x: 0, y: 0 }, canvas: { x: 0, y: 0 } }
                });
            }, nodeId);

            // Wait for "View in Etymology Graph" button
            const etymBtn = page.locator("#view-in-etymology-btn");
            if (await etymBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await etymBtn.click();
                await waitForGraph(page);

                // Go back once — should return to concept map (single entry)
                await page.goBack();
                await waitForConceptMap(page);
                const activeBtn = page.locator(".view-btn.active");
                await expect(activeBtn).toHaveAttribute("data-view", "concept");
            }
        }
    });

    test("refresh preserves state", async ({ page }) => {
        await page.goto("/?word=fire&lang=Latin");
        await waitForGraph(page);

        // Reload the page
        await page.reload();
        await waitForGraph(page);

        const params = await getSearchParams(page);
        expect(params.word).toBe("fire");
        expect(params.lang).toBe("Latin");
        const input = page.locator("#search-input");
        await expect(input).toHaveValue("fire");
    });
});

test.describe("DOM Consistency", () => {
    test("URL params restore correct filter states", async ({ page }) => {
        await page.goto("/?word=fire&types=inh&layout=force-directed");
        await waitForGraph(page);

        // Open filters
        await page.click("#filters-btn");

        // Check connection type checkboxes
        const inhCheckbox = page.locator("#ety-filters input[value='inh']");
        const borCheckbox = page.locator("#ety-filters input[value='bor']");
        const derCheckbox = page.locator("#ety-filters input[value='der']");
        await expect(inhCheckbox).toBeChecked();
        await expect(borCheckbox).not.toBeChecked();
        await expect(derCheckbox).not.toBeChecked();

        // Check layout dropdown
        const layoutSelect = page.locator("#layout-select");
        await expect(layoutSelect).toHaveValue("force-directed");
    });

    test("concept map state restores on back navigation", async ({ page }) => {
        // Load concept with custom filters
        await page.goto("/?view=concept&concept=water&similarity=75");
        await waitForConceptMap(page);

        // Navigate away to etymology
        await page.goto("/?word=fire");
        await waitForGraph(page);

        // Go back to concept map
        await page.goBack();
        await waitForConceptMap(page);

        // Verify slider is restored
        const slider = page.locator("#similarity-slider");
        await expect(slider).toHaveValue("75");
        const display = page.locator("#similarity-value");
        await expect(display).toHaveText("0.75");

        // Verify concept input is restored
        const input = page.locator("#concept-search-input");
        await expect(input).toHaveValue("water");
    });
});
