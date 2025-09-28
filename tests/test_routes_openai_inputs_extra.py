"""Additional input shaping for OpenAI chat route using 'input' field."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_completions_uses_input_when_no_messages(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {"model": "gpt-5", "input": "hi", "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
