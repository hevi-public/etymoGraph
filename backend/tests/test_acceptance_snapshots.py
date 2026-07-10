"""Hermetic acceptance snapshot tests (SPC-00020, over the SPC-00013 corpus).

Runs the full FastAPI app in-process via ``httpx.ASGITransport`` — no live
server, no live Mongo. The Mongo seam (``get_words_collection``) is overridden
with ``FakeWordsCollection`` seeded from each SPC-00013 fixture's ``raw_kaikki``
input doc, and the app's responses are asserted byte-for-byte against the same
fixture's recorded ``system_output``. This turns the live-only characterization
suite (``tests/integration``, marked ``live`` — skips-as-pass when the stack is
down) into a CI-runnable mirror.

Scope (this tier):

* ``word_detail`` and ``chain`` are asserted byte-for-byte. Both derive purely
  from the queried word's own document, so a single seeded doc reproduces them.
* ``tree`` is **not** asserted here: the recorded trees pull descendants and
  cognates from the full 10.4M-doc corpus, which a single-doc seed cannot
  reproduce. Tree coverage lives in the seeded Tier-2/acceptance tests
  (``test_tree_builder.py``, ``test_layout_endpoints.py``) and the live suite.

Language resolution note: ``word_detail``'s ``related_mentions`` and ``chain``'s
ancestor labels resolve language *codes* to *names* via ``lang_cache``, which is
populated from the ``languages`` collection. ``chain`` warms the cache itself;
``word_detail`` does not, so on a cold server ``/api/words/X`` would return codes
(e.g. ``en``) where the warm-server snapshot has names (e.g. ``English``). The
snapshots were collected against a warm, long-running server, so the client
factory warms the cache through the app's own loader (``ensure_loaded`` against
the seeded fake — production code, not a monkeypatch) to reproduce that state.
"""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import httpx
import pytest
from app.database import get_words_collection
from app.main import app
from app.services import lang_cache

from .fakes import FakeWordsCollection

# Repo-root fixtures at <repo>/tests/fixtures/wiktionary (shared with the live
# SPC-00013 suite). This file is at <repo>/backend/tests/.
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wiktionary"

# Seed for the fake `languages` collection. Derived once from the recorded
# fixture outputs (the only codes the 11 fixtures' word_detail + chain must
# resolve); identity/passthrough codes (fa-cls, la-med, roa-oit) are omitted
# because lang_cache returns the code unchanged for unknown entries. If a future
# fixture introduces a new ancestor language, its chain assertion fails loudly
# and the missing code gets added here.
LANGUAGE_DOCS: list[dict[str, str]] = [
    {"lang_code": "ang", "lang": "Old English"},
    {"lang_code": "ar", "lang": "Arabic"},
    {"lang_code": "en", "lang": "English"},
    {"lang_code": "enm", "lang": "Middle English"},
    {"lang_code": "fro", "lang": "Old French"},
    {"lang_code": "gem-pro", "lang": "Proto-Germanic"},
    {"lang_code": "gmw-pro", "lang": "Proto-West Germanic"},
    {"lang_code": "grc", "lang": "Ancient Greek"},
    {"lang_code": "ine-pro", "lang": "Proto-Indo-European"},
    {"lang_code": "itc-pro", "lang": "Proto-Italic"},
    {"lang_code": "la", "lang": "Latin"},
    {"lang_code": "pro", "lang": "Old Occitan"},
    {"lang_code": "sa", "lang": "Sanskrit"},
]


def _fixture_params() -> list:
    """Discover fixture JSONs as pytest params keyed by word."""
    if not FIXTURES_DIR.exists():
        return []
    return [
        pytest.param(json.loads(path.read_text(encoding="utf-8")), id=path.stem)
        for path in sorted(FIXTURES_DIR.glob("*.json"))
    ]


FIXTURE_PARAMS = _fixture_params()


@pytest.fixture
async def make_snapshot_client():
    """Factory: seed the fake from one fixture's raw doc, warm lang_cache the way
    a real long-running server is warm (see module docstring), and return an
    in-process AsyncClient. Overrides cleared and clients closed on teardown.
    """
    clients: list[httpx.AsyncClient] = []

    async def _make(word_doc: dict) -> httpx.AsyncClient:
        fake = FakeWordsCollection([word_doc], languages=list(LANGUAGE_DOCS))
        app.dependency_overrides[get_words_collection] = lambda: fake
        await lang_cache.ensure_loaded(fake)
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        clients.append(client)
        return client

    try:
        yield _make
    finally:
        for client in clients:
            await client.aclose()
        app.dependency_overrides.clear()


def _endpoint(fixture: dict, template: str) -> str:
    """Build a URL path from a fixture's query block. ``template`` may contain ``{w}``."""
    word = urllib.parse.quote(fixture["query"]["word"])
    lang = urllib.parse.quote(fixture["query"]["lang"])
    return f"/api/{template.format(w=word)}?lang={lang}"


@pytest.mark.acceptance
@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
async def test_word_detail_matches_snapshot(fixture: dict, make_snapshot_client) -> None:
    client = await make_snapshot_client(fixture["raw_kaikki"])
    resp = await client.get(_endpoint(fixture, "words/{w}"))
    assert resp.status_code == 200, resp.text
    assert resp.json() == fixture["system_output"]["word_detail"]


@pytest.mark.acceptance
@pytest.mark.parametrize("fixture", FIXTURE_PARAMS)
async def test_chain_matches_snapshot(fixture: dict, make_snapshot_client) -> None:
    client = await make_snapshot_client(fixture["raw_kaikki"])
    resp = await client.get(_endpoint(fixture, "etymology/{w}/chain"))
    assert resp.status_code == 200, resp.text
    assert resp.json() == fixture["system_output"]["chain"]
