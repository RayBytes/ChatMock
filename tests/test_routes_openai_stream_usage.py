"""Stream include_usage path for OpenAI chat route with real translator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield (
            b'data: {"type": "response.output_text.delta", "delta": "Hi", "response": {"id": "r"}}'
        )
        yield (
            b'data: {"type": "response.completed", '
            b'"response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}}}'
        )

    def close(self) -> None:
        return None


def test_chat_completions_stream_include_usage(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert b'"usage": {' in resp.data
