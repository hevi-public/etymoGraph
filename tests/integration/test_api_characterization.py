"""Characterization tests for the etymology API (SPC-00013 Phase 1).

Each test parametrizes over the fixtures in `tests/fixtures/wiktionary/` and
asserts that the live API still returns exactly what was captured when the
fixture was generated. The expected values were collected from this same API,
so a fresh run against the same data MUST pass; a divergence means either the
code or the data changed.

The user validates assertion sensitivity by manually mutating a fixture field
and confirming the corresponding test fails — see SPC-00013 decision-log.md.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "wiktionary"


def _fixture_params() -> list:
    """Discover fixture JSONs and yield them as pytest params keyed by word."""
    if not FIXTURES_DIR.exists():
        return []
    return [
        pytest.param(json.loads(path.read_text(encoding="utf-8")), id=path.stem)
        for path in sorted(FIXTURES_DIR.glob("*.json"))
    ]


def _get(api_base: str, path: str) -> Any:
    """GET a JSON endpoint on the live API and return parsed body.

    Mirrors the collector's `http_get_json`: on HTTPError, returns the
    `__error__` envelope shape that the collector stores in fixtures. This
    keeps snapshot equality meaningful for endpoints that legitimately return
    4xx for some inputs (e.g. /api/concept-map for words without phonetic
    data).
    """
    url = f"{api_base}{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {
            "__error__": f"HTTP {e.code}",
            "url": url,
            "body": e.read().decode("utf-8", errors="replace")[:500],
        }


def _endpoint(fixture: dict, template: str, extra_query: str = "") -> str:
    """Build a URL path from a fixture's query block. `template` may contain `{w}`."""
    word = urllib.parse.quote(fixture["query"]["word"])
    lang = urllib.parse.quote(fixture["query"]["lang"])
    return f"/api/{template.format(w=word)}?lang={lang}{extra_query}"


FIXTURE_PARAMS = _fixture_params()


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_word_detail_matches_snapshot(api_base: str, fixture: dict) -> None:
    actual = _get(api_base, _endpoint(fixture, "words/{w}"))
    assert actual == fixture["system_output"]["word_detail"]


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_chain_matches_snapshot(api_base: str, fixture: dict) -> None:
    actual = _get(api_base, _endpoint(fixture, "etymology/{w}/chain"))
    assert actual == fixture["system_output"]["chain"]


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_tree_inh_matches_snapshot(api_base: str, fixture: dict) -> None:
    actual = _get(api_base, _endpoint(fixture, "etymology/{w}/tree", "&types=inh"))
    assert actual == fixture["system_output"]["tree_inh"]


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_tree_inh_bor_der_cog_matches_snapshot(api_base: str, fixture: dict) -> None:
    actual = _get(api_base, _endpoint(fixture, "etymology/{w}/tree", "&types=inh,bor,der,cog"))
    assert actual == fixture["system_output"]["tree_inh_bor_der_cog"]


# --- Additional endpoint coverage -----------------------------------------
# Snapshot tests for the autocomplete / concept-map surface. The collector
# captures each per fixture-word. Tests skip cleanly when the fixture was
# generated before this coverage existed — regenerate with `make collect-
# fixtures FLAGS=--force` to populate.


def _require_snapshot(fixture: dict, key: str) -> Any:
    snapshot = fixture["system_output"].get(key)
    if snapshot is None:
        pytest.skip(
            f"system_output.{key} not in fixture for "
            f"'{fixture['query']['word']}'; regenerate via `make collect-fixtures`"
        )
    return snapshot


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_search_matches_snapshot(api_base: str, fixture: dict) -> None:
    expected = _require_snapshot(fixture, "search")
    word = urllib.parse.quote(fixture["query"]["word"])
    actual = _get(api_base, f"/api/search?q={word}")
    assert actual == expected


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_concept_suggest_matches_snapshot(api_base: str, fixture: dict) -> None:
    expected = _require_snapshot(fixture, "concept_suggest")
    word = urllib.parse.quote(fixture["query"]["word"])
    actual = _get(api_base, f"/api/concepts/suggest?q={word}")
    assert actual == expected


@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
def test_concept_map_matches_snapshot(api_base: str, fixture: dict) -> None:
    """Captures both success shape and 404 error shape — concept_map returns
    HTTPException for words without phonetic data, which the collector stores
    as an `__error__` payload. Both shapes are valid regression targets.
    """
    expected = _require_snapshot(fixture, "concept_map")
    word = urllib.parse.quote(fixture["query"]["word"])
    actual = _get(api_base, f"/api/concept-map?concept={word}")
    assert actual == expected
