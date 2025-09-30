"""Cover reasoning summary handling in Ollama streaming path."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def __init__(self, events) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_ollama_stream_think_tags_summary_newline_and_close(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["REASONING_COMPAT"] = "think-tags"
    ev = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S1"},
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S2"},
        {"type": "response.completed", "response": {}},
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(ev), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    # The stream returns NDJSON; ensure <think> appears
    assert resp.status_code == 200
    assert b"<think>" in resp.data
