"""Input shaping tests for Ollama chat route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_moves_system_to_front(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        seen["first_role"] = input_items[0]["role"]

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
        "messages": [{"role": "system", "content": "x"}, {"role": "user", "content": "hi"}],
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200
    assert seen["first_role"] == "user"
