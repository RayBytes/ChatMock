"""Stream path tests for OpenAI text completions route."""

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
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_text_completions_stream_path(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {
        "model": "gpt-5",
        "prompt": "hi",
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    assert b"data: [DONE]" in resp.data
