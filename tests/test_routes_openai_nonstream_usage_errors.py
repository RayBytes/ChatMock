"""Cover _extract_usage exception path in OpenAI chat non-stream aggregator."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        # First event has invalid usage fields causing int() to fail inside _extract_usage
        yield (
            b'data: {"type": "response.reasoning_summary_text.delta", "delta": "S", '
            b'"response": {"usage": {"input_tokens": "x"}}}'
        )
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_openai_nonstream_usage_error_is_ignored(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
