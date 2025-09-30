"""Test responses_tool_choice mapping to tool_choice in OpenAI chat route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_openai_responses_tool_choice_none_forwards(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured["tool_choice"] = kw.get("tool_choice")

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tool_choice": "none",
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert captured["tool_choice"] == "none"
