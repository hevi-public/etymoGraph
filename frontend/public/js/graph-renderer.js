/**
 * Graph renderer factory — creates the appropriate adapter based on type.
 * Provides a uniform interface for app.js to render graphs regardless
 * of the underlying library (vis.js, G6, or future renderers).
 */

/* global createVisAdapter, createG6Adapter */

// eslint-disable-next-line no-unused-vars
function createRenderer(type, container) {
    if (type === "g6") {
        return createG6Adapter(container);
    }
    // Default: vis.js
    return createVisAdapter();
}
