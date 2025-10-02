"""Test DEBUG_MODEL override and model normalization in OpenAI chat route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_openai_chat_debug_model_override(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    client.application.config["DEBUG_MODEL"] = "forced"
    seen = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        seen["model"] = model

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    resp = client.post(
        "/v1/chat/completions",
        data=json.dumps(
            {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": True}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert seen["model"] == "forced"
