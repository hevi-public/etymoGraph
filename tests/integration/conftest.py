"""Pytest fixtures for live-API integration tests (SPC-00011 Phase 1)."""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest


@pytest.fixture(scope="session")
def api_base() -> str:
    """Resolve the etymoGraph API base URL and skip the suite if it's unreachable.

    Override with ETYMOGRAPH_API env (default: http://localhost:8000).
    """
    base = os.environ.get("ETYMOGRAPH_API", "http://localhost:8000").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=2) as resp:
            if resp.status != 200:
                pytest.skip(f"API health check at {base} returned {resp.status}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"API not reachable at {base}: {exc}; start services with `make run`")
    return base
