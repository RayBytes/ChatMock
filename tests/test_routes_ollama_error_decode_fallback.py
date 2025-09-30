"""Cover JSON decode fallback path in Ollama error handling."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_upstream_error_decode_fallback_no_tools_verbose(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["VERBOSE"] = True

    class _U:
        status_code = 502
        content = b"not-json"
        text = "bad"

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    data = resp.get_json()
    assert resp.status_code == 502
    assert "error" in data
