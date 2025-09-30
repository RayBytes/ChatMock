"""Non-stream Ollama chat route tests."""

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


def test_ollama_chat_nonstream_basic(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    events = [
        {"type": "response.output_text.delta", "delta": "Hi"},
        {"type": "response.completed", "response": {}},
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(events), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"]["content"] == "Hi"


def test_ollama_chat_upstream_error_no_tools(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()
