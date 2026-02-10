/**
 * URL Router — view-scoped parameter registry with History API integration.
 * Exposes a global `router` object for push/replace/state/initialize.
 * IIFE so const declarations are scoped (enables eval() re-execution in tests).
 */
(function () {
    "use strict";

    var VIEW_PARAMS = {
        etymology: {
            word:     { "default": "wine" },
            lang:     { "default": "English" },
            types:    { "default": "inh,bor,der" },
            layout:   { "default": "era-layered" },
            renderer: { "default": "vis" },
        },
        concept: {
            concept:    { "default": "" },
            pos:        { "default": "" },
            similarity: { "default": 100, parse: Number },
            etymEdges:  { "default": true, parse: function (v) { return v !== "false"; } },
        },
    };
    var DEFAULT_VIEW = "etymology";

    /** Serialize state to a full query string (all params always included). */
    function buildURL(state) {
        var view = state.view || DEFAULT_VIEW;
        var defs = VIEW_PARAMS[view];
        if (!defs) return "/";

        var params = new URLSearchParams();
        params.set("view", view);
        for (var key in defs) {
            var val = (state[key] !== undefined) ? state[key] : defs[key]["default"];
            params.set(key, val);
        }
        return "/?" + params.toString();
    }

    /** Deserialize URL search string into state. Accepts optional string for testability. */
    function parseURL(search) {
        var raw = (search !== undefined) ? search : window.location.search;
        var params = new URLSearchParams(raw);
        var view = params.get("view") || DEFAULT_VIEW;

        // Fall back to default view if unknown
        if (!VIEW_PARAMS[view]) {
            view = DEFAULT_VIEW;
        }

        var defs = VIEW_PARAMS[view];
        var state = { view: view };
        for (var key in defs) {
            var urlVal = params.get(key);
            if (urlVal !== null && defs[key].parse) {
                state[key] = defs[key].parse(urlVal);
            } else if (urlVal !== null) {
                state[key] = urlVal;
            } else {
                state[key] = defs[key]["default"];
            }
        }
        return state;
    }

    // Internal cache: current URL string + parsed state
    var _currentURL = "/";
    var _currentState = null;
    var _navigateCallback = null;

    function initialize() {
        _currentState = parseURL();
        _currentURL = buildURL(_currentState);
        window.history.replaceState(_currentState, "", _currentURL);

        window.addEventListener("popstate", function (e) {
            _currentState = e.state || parseURL();
            _currentURL = buildURL(_currentState);
            if (_navigateCallback) {
                _navigateCallback(_currentState);
            }
        });
    }

    /** Register popstate callback. Single-consumer: replaces any previous callback. */
    function onNavigate(cb) {
        _navigateCallback = cb;
    }

    function push(params) {
        var merged = _mergeParams(params);
        var url = buildURL(merged);
        if (url === _currentURL) return; // duplicate prevention
        _currentState = merged;
        _currentURL = url;
        window.history.pushState(merged, "", url);
    }

    function replace(params) {
        var merged = _mergeParams(params);
        var url = buildURL(merged);
        _currentState = merged;
        _currentURL = url;
        window.history.replaceState(merged, "", url);
    }

    function state() {
        return Object.assign({}, _currentState);
    }

    /** Merge partial params with current state. On view change, fill new view's defaults. */
    function _mergeParams(params) {
        var base = _currentState || parseURL();
        var view = params.view || base.view || DEFAULT_VIEW;
        var viewChanged = view !== base.view;

        // Start from current state or fresh defaults for new view
        var merged = { view: view };
        var defs = VIEW_PARAMS[view];
        if (!defs) return merged;

        if (viewChanged) {
            // Fill defaults for new view
            for (var key in defs) {
                merged[key] = defs[key]["default"];
            }
        } else {
            // Carry over current view params
            for (var key2 in defs) {
                merged[key2] = (base[key2] !== undefined) ? base[key2] : defs[key2]["default"];
            }
        }

        // Apply incoming params (only those valid for this view)
        for (var pkey in params) {
            if (pkey === "view") continue;
            if (defs[pkey] !== undefined) {
                merged[pkey] = params[pkey];
            }
        }

        return merged;
    }

    window.router = {
        initialize: initialize,
        onNavigate: onNavigate,
        push: push,
        replace: replace,
        state: state,
        _internals: {
            VIEW_PARAMS: VIEW_PARAMS,
            DEFAULT_VIEW: DEFAULT_VIEW,
            parseURL: parseURL,
            buildURL: buildURL,
        },
    };
})();
