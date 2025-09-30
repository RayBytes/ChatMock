"""Tests toggling DEFAULT_WEB_SEARCH in Ollama route and responses_tool_choice none."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_default_web_search_injected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["DEFAULT_WEB_SEARCH"] = True
    seen = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        seen.update(kw)

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert any(t.get("type") == "web_search" for t in seen.get("tools", []))


def test_ollama_responses_tool_choice_none(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured["tool_choice"] = kw.get("tool_choice")

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tool_choice": "none",
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert captured["tool_choice"] == "none"
