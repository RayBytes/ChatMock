"""Ollama streaming route with o3 reasoning mode."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {"type": "response.reasoning_summary_text.delta", "delta": "S"}'
        yield b'data: {"type": "response.reasoning_text.delta", "delta": "F"}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_ollama_stream_o3_reasoning(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    client.application.config["REASONING_COMPAT"] = "o3"
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert b'"content":' in resp.data
