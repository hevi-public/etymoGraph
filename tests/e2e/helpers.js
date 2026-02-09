/**
 * Shared E2E test utilities for Etymology Explorer.
 */

/** Wait until the etymology graph has rendered nodes. */
export async function waitForGraph(page, timeout = 15000) {
    await page.waitForFunction(
        () => typeof window.network !== "undefined"
            && window.network !== null
            && window.network.body.data.nodes.length > 0,
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
