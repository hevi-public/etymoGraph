/**
 * vis.js renderer adapter — wraps existing graph.js functions behind the
 * renderer abstraction interface. This is a thin delegation layer; all
 * vis.js logic remains in graph.js.
 */

/* global updateGraph, selectNodeById, LAYOUTS, currentLayout */

// eslint-disable-next-line no-unused-vars
function createVisAdapter() {
    return {
        type: "vis",

        render(data) {
            updateGraph(data);
            return Promise.resolve();
        },

        destroy() {
            // updateGraph destroys the previous network internally
        },

        selectNode(nodeId) {
            selectNodeById(nodeId);
        },

        getAvailableLayouts() {
            return Object.keys(LAYOUTS);
        },

        getCurrentLayout() {
            return currentLayout;
        },
    };
}
