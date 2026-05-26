"""Negative-path and boundary tests over the API surface (SPC-00013).

These pin down behavior on inputs the snapshot suite doesn't cover: words
that don't exist, malformed queries, parameter boundaries, empty filters.
The kind of edges refactors most often regress.

Run against the live API (require `make run`); no fixtures involved.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

NONEXISTENT_WORD = "ZzzNonexistentWordForNegativeTestXYZ"
NONEXISTENT_LANG = "ZzzNonexistentLangForNegativeTestXYZ"


def _request(api_base: str, path: str) -> tuple[int, Any]:
    """Return (status_code, parsed_body) for a GET against the live API.

    Distinct from test_api_characterization's `_get` because here we need
    the status code as part of the assertion, not as an error envelope.
    """
    url = f"{api_base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = None
        return e.code, body


# --- /api/words/{word} negative paths ------------------------------------


def test_words_nonexistent_word_returns_404(api_base: str) -> None:
    status, body = _request(api_base, f"/api/words/{NONEXISTENT_WORD}")
    assert status == 404
    assert body and "detail" in body
    assert NONEXISTENT_WORD in body["detail"]


def test_words_real_word_wrong_lang_returns_404(api_base: str) -> None:
    qs = urllib.parse.quote(NONEXISTENT_LANG)
    status, body = _request(api_base, f"/api/words/wine?lang={qs}")
    assert status == 404
    assert body and NONEXISTENT_LANG in body["detail"]


# --- /api/etymology/{w}/chain negative paths -----------------------------


def test_chain_nonexistent_word_returns_empty_chain(api_base: str) -> None:
    """Per backend/app/routers/etymology.py, missing words yield a 1-node
    chain (the query word) with zero edges — not a 404."""
    status, body = _request(api_base, f"/api/etymology/{NONEXISTENT_WORD}/chain")
    assert status == 200
    assert body and body.get("edges") == []
    nodes = body.get("nodes") or []
    assert len(nodes) == 1
    assert nodes[0]["label"] == NONEXISTENT_WORD
    assert nodes[0]["level"] == 0


# --- /api/etymology/{w}/tree parameter boundaries ------------------------


def test_tree_descendant_depth_at_upper_bound(api_base: str) -> None:
    """max_descendant_depth=5 is the documented upper bound — must succeed."""
    status, body = _request(
        api_base,
        "/api/etymology/wine/tree?max_descendant_depth=5",
    )
    assert status == 200
    assert isinstance(body.get("nodes"), list)


def test_tree_descendant_depth_above_upper_bound_rejected(api_base: str) -> None:
    """max_descendant_depth=6 must be rejected (422) — FastAPI Query(le=5)."""
    status, body = _request(
        api_base,
        "/api/etymology/wine/tree?max_descendant_depth=6",
    )
    assert status == 422
    assert body and "detail" in body


def test_tree_descendant_depth_below_lower_bound_rejected(api_base: str) -> None:
    """max_descendant_depth=0 must be rejected (422) — FastAPI Query(ge=1)."""
    status, _ = _request(
        api_base,
        "/api/etymology/wine/tree?max_descendant_depth=0",
    )
    assert status == 422


def test_tree_empty_types_defaults_to_inh(api_base: str) -> None:
    """Empty types= must NOT crash — the router falls back to {'inh'}."""
    status, body = _request(api_base, "/api/etymology/wine/tree?types=")
    assert status == 200
    assert isinstance(body.get("nodes"), list)


def test_tree_garbage_types_defaults_to_inh(api_base: str) -> None:
    """All-invalid types= falls back to {'inh'} too."""
    status, body = _request(
        api_base,
        "/api/etymology/wine/tree?types=garbage,also-garbage",
    )
    assert status == 200
    assert isinstance(body.get("nodes"), list)


# --- /api/search parameter boundaries ------------------------------------


def test_search_empty_query_rejected(api_base: str) -> None:
    """q is Query(..., min_length=1) — empty must yield 422."""
    status, body = _request(api_base, "/api/search?q=")
    assert status == 422
    assert body and "detail" in body


def test_search_missing_query_rejected(api_base: str) -> None:
    """q is required — omitted must yield 422."""
    status, _ = _request(api_base, "/api/search")
    assert status == 422


def test_search_limit_zero_rejected(api_base: str) -> None:
    """limit is Query(ge=1) — zero must yield 422."""
    status, _ = _request(api_base, "/api/search?q=wine&limit=0")
    assert status == 422


def test_search_limit_above_max_rejected(api_base: str) -> None:
    """limit is Query(le=100) — 101 must yield 422."""
    status, _ = _request(api_base, "/api/search?q=wine&limit=101")
    assert status == 422


def test_search_nonexistent_prefix_returns_empty(api_base: str) -> None:
    qs = urllib.parse.quote(NONEXISTENT_WORD)
    status, body = _request(api_base, f"/api/search?q={qs}")
    assert status == 200
    assert body.get("results") == []
    assert body.get("total") == 0


# --- /api/concept-map negative paths -------------------------------------


def test_concept_map_nonexistent_concept_returns_404(api_base: str) -> None:
    qs = urllib.parse.quote(NONEXISTENT_WORD)
    status, body = _request(api_base, f"/api/concept-map?concept={qs}")
    assert status == 404
    assert body and "detail" in body


def test_concept_map_missing_concept_rejected(api_base: str) -> None:
    status, _ = _request(api_base, "/api/concept-map")
    assert status == 422


# --- /api/concepts/suggest negative paths --------------------------------


def test_concept_suggest_empty_query_rejected(api_base: str) -> None:
    status, _ = _request(api_base, "/api/concepts/suggest?q=")
    assert status == 422


def test_concept_suggest_nonexistent_prefix_returns_empty(api_base: str) -> None:
    qs = urllib.parse.quote(NONEXISTENT_WORD)
    status, body = _request(api_base, f"/api/concepts/suggest?q={qs}")
    assert status == 200
    assert body.get("suggestions") == []


# --- /health (smoke) -----------------------------------------------------


def test_health_returns_ok(api_base: str) -> None:
    """The /health endpoint that conftest already pings — pin it down."""
    status, body = _request(api_base, "/health")
    assert status == 200
    assert body == {"status": "ok"}
