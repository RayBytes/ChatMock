"""Test non-stream Text Completions includes usage in final response."""

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


def test_completions_nonstream_usage_present(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "prompt": "hi"}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json().get("usage", {}).get("total_tokens") == 3
