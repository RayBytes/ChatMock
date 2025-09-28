"""Responses tools behavior for Ollama routes."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_ollama as routes


def test_ollama_responses_tools_unsupported(client: object) -> None:
    body = {"model": "gpt-5", "messages": [], "responses_tools": [{"type": "other"}]}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400


def test_ollama_responses_tools_too_large(client: object) -> None:
    big = "x" * 40000
    body = {
        "model": "gpt-5",
        "messages": [],
        "responses_tools": [{"type": "web_search", "big": big}],
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400


def test_ollama_responses_tools_fallback_on_error(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    class _U1:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    class _U2:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    def fake_start(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (_U1(), None) if calls["n"] == 1 else (_U2(), None)

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200 and calls["n"] == 2
