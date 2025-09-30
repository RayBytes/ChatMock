"""Non-stream Chat Completions should include tool_calls in final message."""

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
            b'data: {"type": "response.output_item.done", '
            b'"item": {"type": "function_call", "id": "c1", "name": "fn", '
            b'"arguments": "{\\"a\\":1}"}, "response": {"id": "r"}}'
        )
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_openai_nonstream_includes_tool_calls(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["choices"][0]["message"].get("tool_calls")
