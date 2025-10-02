"""Exercise verbose logging path when responses tools are rejected for Ollama route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_responses_tools_fallback_verbose_logs(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["VERBOSE"] = True

    class _U1:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    calls = {"n": 0}

    def fake_start(*a: Any, **k: Any):
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
    assert resp.status_code == 400
