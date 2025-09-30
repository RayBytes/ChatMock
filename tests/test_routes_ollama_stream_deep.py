"""Deep streaming path coverage for Ollama chat route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_ollama_chat_stream_deep_branches(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    ev = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "web_search_call.delta", "item_id": "ws1", "item": {"parameters": {"q": "x"}}},
        {"type": "web_search_call.completed", "item_id": "ws1"},
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "c1", "name": "fn", "arguments": {"a": 1}},
        },
        {"type": "response.output_text.delta", "delta": "Hello"},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        },
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(ev), None), raising=True
    )
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"function": {"name": "fn"}}],
        "stream": True,
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert b"<think>" in resp.data
