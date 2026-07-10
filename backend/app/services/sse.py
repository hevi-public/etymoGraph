"""Server-Sent Events framing for the layout streaming endpoints (SPC-00021).

Hand-rolled (no dependency): an SSE message is an ``event:`` line, one or more
``data:`` lines, and a blank-line terminator; ``:``-prefixed lines are comments
used here as heartbeats. These are pure string builders, unit-tested at Tier 0 —
the only knowledge of the wire format lives here so the router stays about
orchestration, not byte layout.
"""

import json


def format_event(event: str, data: dict) -> str:
    """Frame one named SSE event with a compact-JSON ``data`` payload.

    Args:
        event: The SSE event name (``graph``/``frame``/``final``/``error``).
        data: JSON-serializable payload. Serialized compactly; ``json.dumps``
            escapes any embedded newline so the single ``data:`` line never
            breaks the frame.

    Returns:
        The full SSE frame including its trailing blank line.
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def format_comment(text: str) -> str:
    """Frame an SSE comment line (``: text``), used as a heartbeat.

    EventSource clients ignore comment lines; they exist only to keep the
    connection (and any intermediary proxy) from idling out mid-solve.
    """
    return f": {text}\n\n"
