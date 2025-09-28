"""Ensure stream_options.include_usage is forwarded for Text Completions stream."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_text_completions_stream_forwards_include_usage(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = {}

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self) -> None:
            return None

    def fake_sse(up, model, created, *, verbose=False, vlog=None, include_usage=False):  # type: ignore[no-untyped-def]
        seen["include_usage"] = include_usage
        return [b"data: [DONE]\n\n"]

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    monkeypatch.setattr(routes, "sse_translate_text", fake_sse, raising=True)
    body = {
        "model": "gpt-5",
        "prompt": "hi",
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200 and seen["include_usage"] is True
