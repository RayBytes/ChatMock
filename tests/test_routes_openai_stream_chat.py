"""Stream path tests for OpenAI chat route, using a patched SSE generator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b"data: {}"

    def close(self) -> None:
        return None


def _fake_sse(*args, **kwargs):  # type: ignore[no-untyped-def]
    yield b'data: {"hello":1}\n\n'
    yield b"data: [DONE]\n\n"


def test_chat_completions_stream_minimal(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    monkeypatch.setattr(routes, "sse_translate_chat", _fake_sse, raising=True)
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    assert b"data: [DONE]" in resp.data
