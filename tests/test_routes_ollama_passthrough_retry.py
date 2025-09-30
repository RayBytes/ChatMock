"""Cover passthrough retry branch when upstream rejects extra tools."""

from __future__ import annotations

import json
from collections.abc import Iterator


class _U:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""
        self.content = b""

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        yield b'data: {"type": "response.completed"}'

    def close(self) -> None:
        return None


def test_passthrough_retry_succeeds_without_extra_tools(client):
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "responses_tools": [{"type": "web_search"}],
    }

    import chatmock.routes_ollama as routes

    calls = {"n": 0}

    def fake_start(model, input_items, **kw):
        calls["n"] += 1
        # First call returns 400 when extra tools included; second succeeds
        return (_U(400) if calls["n"] == 1 else _U(200)), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig
