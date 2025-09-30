"""Cover invalid JSON event branch in non-stream Ollama aggregator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b"data: {bad json}"
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_ollama_nonstream_invalid_json_event_ignored(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
