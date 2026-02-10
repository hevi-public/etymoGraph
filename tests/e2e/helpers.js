/**
 * Shared E2E test utilities for Etymology Explorer.
 */

/** Wait until the etymology graph has rendered nodes. */
export async function waitForGraph(page, timeout = 15000) {
    await page.waitForFunction(
        () => typeof window.__etymoNetwork !== "undefined"
            && window.__etymoNetwork !== null
            && window.__etymoNetwork.body.data.nodes.length > 0,
        { timeout }
    );
}

/** Wait until the concept map has rendered nodes. */
export async function waitForConceptMap(page, timeout = 15000) {
    await page.waitForFunction(
        () => typeof window.conceptNetwork !== "undefined"
            && window.conceptNetwork !== null
            && window.conceptNetwork.body.data.nodes.length > 0,
        { timeout }
    );
}

/** Return the number of nodes in the etymology graph. */
export async function getNodeCount(page) {
    return await page.evaluate(() => {
        if (!window.__etymoNodesDS) return 0;
        return window.__etymoNodesDS.length;
    });
}

/** Zoom to a target scale by dispatching Ctrl+wheel events on the graph container. */
export async function zoomToScale(page, targetScale, { maxSteps = 100 } = {}) {
    const graphEl = await page.locator("#graph");
    let steps = 0;
    while (steps < maxSteps) {
        const currentScale = await page.evaluate(() => {
            return window.__etymoNetwork ? window.__etymoNetwork.getScale() : 1;
        });
        if (Math.abs(currentScale - targetScale) < 0.02) break;
        const deltaY = currentScale > targetScale ? 10 : -10;
        await graphEl.dispatchEvent("wheel", {
            deltaY,
            ctrlKey: true,
            bubbles: true,
        });
        await page.waitForTimeout(20);
        steps++;
    }
}

/** Return the current URL search params as a plain object. */
export async function getSearchParams(page) {
    return await page.evaluate(() => {
        const params = {};
        new URLSearchParams(window.location.search).forEach((v, k) => {
            params[k] = v;
        });
        return params;
    });
}
