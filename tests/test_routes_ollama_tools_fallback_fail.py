"""Cover Ollama chat tools fallback failure path returning RESPONSES_TOOLS_REJECTED."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_tools_fallback_failure_returns_rejected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U1:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    calls = {"n": 0}

    def fake_start(*a: Any, **k: Any):
        # First call returns error; second call returns (None, error_resp)
        calls["n"] += 1
        if calls["n"] == 1:
            return _U1(), None
        return None, (routes.jsonify({"error": {"message": "bad2"}}), 502)

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    data = resp.get_json()
    assert resp.status_code == 400
    assert data.get("error", {}).get("code") == "RESPONSES_TOOLS_REJECTED"
