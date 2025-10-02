"""Non-stream Ollama route should apply <think> reasoning in final content."""

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
        yield b'data: {"type": "response.output_text.delta", "delta": "Hello"}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_ollama_nonstream_reasoning_think_tags(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["message"]["content"].startswith("<think>")
