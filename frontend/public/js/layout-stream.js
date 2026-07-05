/**
 * Server-side layout streaming (SPC-00021 Phase 3+4).
 *
 * Thin, view-agnostic glue between the SSE layout endpoints and vis.js:
 *   - `getLayoutMode()`      — resolves the server|client feature flag.
 *   - `openLayoutStream(url, handlers)` — a singleton EventSource wrapper that
 *     dispatches `graph`/`frame`/`final`/`error` events, guards a first-`graph`
 *     timeout, and never lets EventSource's auto-reconnect re-run a solve.
 *   - `createPositionTween(nodesDataSet)` — a single rAF loop that tweens node
 *     positions between streamed frames (the frames carry the FA2 dynamics; we
 *     only interpolate between them). Nodes being dragged are user-owned and
 *     skipped.
 *
 * The math (`interpolatePositions`, easings) is pure and exported on `window`
 * for the Vitest eval harness. IIFE so `const`s stay scoped (re-evaluable in
 * tests), mirroring router.js.
 */
(function () {
    "use strict";

    // --- feature flag ------------------------------------------------------

    /**
     * Resolve the layout mode. Precedence: URL `?layoutMode=` > localStorage
     * `layoutMode` > "client" (the Phase 3+4 default; Phase 5 flips it). The
     * resolved value is mirrored on `window.__layoutMode` for E2E assertions.
     * @returns {"server"|"client"}
     */
    function getLayoutMode() {
        var mode = null;
        try {
            var param = new URLSearchParams(window.location.search).get("layoutMode");
            if (param === "server" || param === "client") {
                mode = param;
            } else if (window.localStorage) {
                var stored = window.localStorage.getItem("layoutMode");
                if (stored === "server" || stored === "client") mode = stored;
            }
        } catch {
            // location/localStorage may be unavailable in some test contexts.
        }
        mode = mode || "client";
        window.__layoutMode = mode;
        return mode;
    }

    // --- pure tween math (exported for tests) ------------------------------

    function easeLinear(t) {
        return t;
    }

    /** Ease-out cubic — used for the settle onto the terminal `final` frame. */
    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    var EASINGS = { linear: easeLinear, easeOut: easeOutCubic };

    /** Normalize a position (`[x,y]` from the wire or `{x,y}` from vis) to `{x,y}`. */
    function toXY(value) {
        if (Array.isArray(value)) return { x: value[0], y: value[1] };
        return { x: value.x, y: value.y };
    }

    /**
     * Interpolate node positions from `start` toward `end` at progress `t`.
     * Returns a vis-DataSet update array `[{id,x,y}]` for every id in `end`,
     * except ids in `skip` (being dragged). Ids new in `end` (absent from
     * `start`) snap straight to their target, so filter changes place new nodes
     * without a fly-in from the origin.
     * @param {Object} start id → {x,y} (or [x,y])
     * @param {Object} end   id → {x,y} (or [x,y])
     * @param {number} t     raw progress in [0,1]
     * @param {Function} [easing] maps raw t → eased t (default linear)
     * @param {Set} [skip]   ids to omit (dragged nodes)
     * @returns {Array<{id:string,x:number,y:number}>}
     */
    function interpolatePositions(start, end, t, easing, skip) {
        var ease = easing || easeLinear;
        var f = ease(Math.max(0, Math.min(1, t)));
        var updates = [];
        for (var id in end) {
            if (!Object.prototype.hasOwnProperty.call(end, id)) continue;
            if (skip && typeof skip.has === "function" && skip.has(id)) continue;
            var to = toXY(end[id]);
            var from = start[id] !== undefined ? toXY(start[id]) : to;
            updates.push({
                id: id,
                x: from.x + (to.x - from.x) * f,
                y: from.y + (to.y - from.y) * f,
            });
        }
        return updates;
    }

    // --- position tween controller ----------------------------------------

    /**
     * A single rAF loop that tweens a vis DataSet toward successive target
     * position maps. Each `tweenTo` restarts the interpolation from the current
     * on-screen positions, so mid-flight targets chain smoothly.
     * @param {{update:Function}} nodesDataSet vis.DataSet of nodes
     * @param {Object} [opts] injection seams for tests: getSkip, now, raf, caf
     */
    function createPositionTween(nodesDataSet, opts) {
        opts = opts || {};
        var getSkip = opts.getSkip || function () { return null; };
        var now = opts.now || function () {
            return (window.performance && window.performance.now)
                ? window.performance.now() : Date.now();
        };
        var raf = opts.raf || (window.requestAnimationFrame
            ? window.requestAnimationFrame.bind(window)
            : function (cb) { return setTimeout(function () { cb(now()); }, 16); });
        var caf = opts.caf || (window.cancelAnimationFrame
            ? window.cancelAnimationFrame.bind(window)
            : clearTimeout);

        var current = {};   // id → {x,y} last applied on screen
        var startPos = {};  // id → {x,y} at the current tween's start
        var endPos = {};    // id → {x,y} current target
        var startT = 0;
        var durationMs = 0;
        var easing = easeLinear;
        var rafId = null;
        var running = false;

        function step() {
            var t = durationMs > 0 ? (now() - startT) / durationMs : 1;
            var skip = getSkip();
            var updates = interpolatePositions(startPos, endPos, t, easing, skip);
            for (var i = 0; i < updates.length; i++) {
                current[updates[i].id] = { x: updates[i].x, y: updates[i].y };
            }
            if (updates.length) nodesDataSet.update(updates);
            if (t >= 1) {
                running = false;
                rafId = null;
                return;
            }
            rafId = raf(step);
        }

        /** Seed on-screen positions without animating (e.g. from getPositions()). */
        function seedCurrent(positions) {
            current = {};
            for (var id in positions) {
                if (Object.prototype.hasOwnProperty.call(positions, id)) {
                    current[id] = toXY(positions[id]);
                }
            }
        }

        /**
         * Merge specific positions into the on-screen baseline without clearing
         * the rest — used to re-sync a node the user just finished dragging, so a
         * frame arriving mid-drag doesn't snap it back to its pre-drag spot.
         */
        function syncCurrent(positions) {
            for (var id in positions) {
                if (Object.prototype.hasOwnProperty.call(positions, id)) {
                    current[id] = toXY(positions[id]);
                }
            }
        }

        /**
         * Animate toward `targetPositions` starting from the current positions.
         * @param {Object} targetPositions id → [x,y] or {x,y}
         * @param {{durationMs?:number, easing?:string|Function}} [options]
         */
        function tweenTo(targetPositions, options) {
            options = options || {};
            startPos = {};
            for (var id in current) {
                if (Object.prototype.hasOwnProperty.call(current, id)) startPos[id] = current[id];
            }
            endPos = {};
            for (var k in targetPositions) {
                if (Object.prototype.hasOwnProperty.call(targetPositions, k)) {
                    endPos[k] = toXY(targetPositions[k]);
                    // Ensure `current` tracks new nodes so the next tween chains.
                    if (current[k] === undefined) current[k] = endPos[k];
                }
            }
            startT = now();
            durationMs = options.durationMs != null ? options.durationMs : 150;
            easing = typeof options.easing === "function"
                ? options.easing
                : (EASINGS[options.easing] || easeLinear);
            if (!running) {
                running = true;
                rafId = raf(step);
            }
        }

        function stop() {
            if (rafId != null) caf(rafId);
            rafId = null;
            running = false;
        }

        return {
            tweenTo: tweenTo,
            seedCurrent: seedCurrent,
            syncCurrent: syncCurrent,
            stop: stop,
            isRunning: function () { return running; },
            getCurrent: function () { return current; },
        };
    }

    // --- SSE stream wrapper ------------------------------------------------

    var _es = null;         // singleton EventSource
    var _graphTimer = null;

    function _clearGraphTimer() {
        if (_graphTimer) {
            clearTimeout(_graphTimer);
            _graphTimer = null;
        }
    }

    /** Close the active layout stream (view switch, teardown, or before a new one). */
    function closeLayoutStream() {
        _clearGraphTimer();
        if (_es) {
            _es.close();
            _es = null;
        }
    }

    function _safeParse(text) {
        try {
            return JSON.parse(text);
        } catch {
            return {};
        }
    }

    /**
     * Open an SSE layout stream. Singleton: any previous stream is closed first.
     * Handlers: onGraph(payload), onFrame(payload), onFinal(payload),
     * onError({message}). `graphTimeoutMs` (default 10000) bounds the wait for
     * the first `graph` event before declaring failure (→ onError → fallback).
     * @returns {EventSource|null}
     */
    function openLayoutStream(url, handlers) {
        handlers = handlers || {};
        closeLayoutStream();

        var graphTimeoutMs = handlers.graphTimeoutMs != null ? handlers.graphTimeoutMs : 10000;
        var gotGraph = false;
        var finished = false;
        var es;
        try {
            es = new EventSource(url);
        } catch (e) {
            if (handlers.onError) handlers.onError({ message: String(e) });
            return null;
        }
        _es = es;

        function finish() {
            finished = true;
            closeLayoutStream();
        }

        _graphTimer = setTimeout(function () {
            if (!gotGraph && !finished) {
                finish();
                if (handlers.onError) handlers.onError({ message: "graph timeout" });
            }
        }, graphTimeoutMs);

        es.addEventListener("graph", function (ev) {
            if (finished) return;
            gotGraph = true;
            _clearGraphTimer();
            if (handlers.onGraph) handlers.onGraph(_safeParse(ev.data));
        });

        es.addEventListener("frame", function (ev) {
            if (finished) return;
            if (handlers.onFrame) handlers.onFrame(_safeParse(ev.data));
        });

        es.addEventListener("final", function (ev) {
            if (finished) return;
            var payload = _safeParse(ev.data);
            // Close BEFORE invoking the handler so EventSource's post-close
            // `error` (fired when the server drops the connection) can't trigger
            // an auto-reconnect that would re-run the whole solve.
            finish();
            if (handlers.onFinal) handlers.onFinal(payload);
        });

        // Fires for BOTH a server-sent `event: error` (has data) and any
        // transport failure/close (no data). A drop after we already finished is
        // normal end-of-stream — ignore it.
        es.addEventListener("error", function (ev) {
            if (finished) return;
            var message = (ev && ev.data) ? (_safeParse(ev.data).message || "stream error")
                : "stream error";
            finish();
            if (handlers.onError) handlers.onError({ message: message });
        });

        return es;
    }

    // --- exports -----------------------------------------------------------

    window.getLayoutMode = getLayoutMode;
    window.openLayoutStream = openLayoutStream;
    window.closeLayoutStream = closeLayoutStream;
    window.createPositionTween = createPositionTween;
    // Pure helpers exposed for the Vitest eval harness.
    window.interpolatePositions = interpolatePositions;
    window.__layoutStreamInternals = {
        easeLinear: easeLinear,
        easeOutCubic: easeOutCubic,
        toXY: toXY,
        EASINGS: EASINGS,
    };
})();
