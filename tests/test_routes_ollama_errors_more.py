"""Additional Ollama route error branches to improve coverage."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_ollama as routes


def test_ollama_invalid_request_format(client: object) -> None:
    # messages must be a non-empty list
    resp = client.post(
        "/api/chat",
        data=json.dumps({"model": "gpt-5", "messages": []}),
        content_type="application/json",
    )
    assert resp.status_code == 400 and resp.get_json().get("error") == "Invalid request format"


def test_ollama_upstream_error_no_tools_verbose(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["VERBOSE"] = True

    class _U:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    data = resp.get_json()
    assert resp.status_code == 400 and "error" in data
