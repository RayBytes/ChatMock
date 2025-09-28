"""Ensure text completions non-stream ignores non-data lines in SSE."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_completions_nonstream_ignores_noise(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U:
        status_code = 200
        content = b""
        text = ""

        def iter_lines(self, decode_unicode: bool = False):
            yield b"event: ping"
            yield b'data: {"type": "response.output_text.delta", "delta": "hi"}'
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)

    body = {"model": "gpt-5", "prompt": "hello", "stream": False}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
