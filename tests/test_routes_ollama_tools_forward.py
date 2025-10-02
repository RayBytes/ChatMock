"""Ensure Ollama tools are normalized and forwarded to upstream."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_tools_forwarding(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured["tools"] = kw.get("tools")

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
        "tools": [
            {"function": {"name": "a"}},
            {"name": "b"},
        ],
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert [t.get("type") for t in captured["tools"]] == [
        "function",
        "function",
    ]
