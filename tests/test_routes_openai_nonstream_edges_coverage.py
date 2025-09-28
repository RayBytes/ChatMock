"""Exercise non-stream chat and text loops to cover branch edges."""

from __future__ import annotations

import json

import chatmock.routes_openai as routes


class _U:
    status_code = 200
    content = b""
    text = ""

    def __init__(self, lines):
        self._lines = list(lines)

    def iter_lines(self, decode_unicode: bool = False):
        for ln in self._lines:
            yield ln

    def close(self):
        return None


def test_chat_nonstream_loop_edges(client):
    # Prepare upstream with various edges: empty, non-data, blank data, invalid JSON, non-function item, delta, completed
    lines = [
        b"",  # not raw
        b"event: ping",  # not data line
        b"data: ",  # blank data
        b"data: {invalid",  # invalid json
        b'data: {"type": "response.output_item.done", "item": {"type": "message"}}',
        b'data: {"type": "response.output_text.delta", "delta": "hi"}',
        b'data: {"type": "response.completed", "response": {"usage": {}}}',
    ]

    def fake_start(model, input_items, **kw):
        return _U(lines), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
        resp = client.post(
            "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
        )
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig


def test_text_nonstream_loop_edges(client):
    lines = [
        b"",  # not raw
        b"event: ping",
        b"data: ",
        b"data: {invalid",
        b'data: {"type": "response.output_text.delta", "delta": "hi"}',
        b"data: [DONE]",
        b'data: {"type": "response.completed", "response": {}}',
    ]

    def fake_start(model, input_items, **kw):
        return _U(lines), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        body = {"model": "gpt-5", "prompt": "hello", "stream": False}
        resp = client.post(
            "/v1/completions", data=json.dumps(body), content_type="application/json"
        )
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig
