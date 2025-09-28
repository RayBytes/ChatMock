"""Test responses_tool_choice mapping to tool_choice for Ollama route."""

from __future__ import annotations

import json
from typing import Any

import pytest

import chatmock.routes_ollama as routes


def test_ollama_responses_tool_choice_none_forwards(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_start(model: str, input_items: list[dict[str, Any]], **kw: Any):
        captured.update(kw)

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
        "stream": True,
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200 and captured.get("tool_choice") == "none"
