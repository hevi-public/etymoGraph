"""Tier 0 tests for the SSE wire-format helpers (SPC-00021)."""

import json

import pytest
from app.services import sse


@pytest.mark.tier0
def test_format_event_frames_name_and_compact_json():
    assert sse.format_event("graph", {"a": 1}) == 'event: graph\ndata: {"a":1}\n\n'


@pytest.mark.tier0
def test_format_event_data_roundtrips_as_json():
    payload = {"i": 3, "positions": {"cheese:English": [1.5, -2.0]}}
    out = sse.format_event("frame", payload)
    lines = out.split("\n")
    assert lines[0] == "event: frame"
    assert json.loads(lines[1].removeprefix("data: ")) == payload
    assert out.endswith("\n\n")


@pytest.mark.tier0
def test_format_event_escapes_embedded_newlines():
    """A newline inside a value must be JSON-escaped, never a literal newline
    that would split the SSE frame (only the 3 framing newlines are real)."""
    out = sse.format_event("error", {"message": "line1\nline2"})
    assert out.count("\n") == 3


@pytest.mark.tier0
def test_format_comment_is_colon_prefixed_heartbeat():
    assert sse.format_comment("ping") == ": ping\n\n"
