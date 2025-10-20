"""Exercise Ollama non-stream loop edges to improve branch coverage."""

from __future__ import annotations

import json

import chatmock.routes_ollama as routes


class _U:
    status_code = 200
    content = b""
    text = ""

    def __init__(self, lines) -> None:
        self._lines = list(lines)

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self):
        return None


def test_ollama_chat_nonstream_loop_edges(client):
    lines = [
        b"",  # not raw
        b"event: ping",
        b"data: ",
        b"data: {invalid",
        b'data: {"type": "response.output_item.done", "item": {"type": "message"}}',
        b'data: {"type": "response.output_text.delta", "delta": "hi"}',
        b'data: {"type": "response.completed"}',
    ]

    def fake_start(model, input_items, **kw):
        return _U(lines), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
        resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig
