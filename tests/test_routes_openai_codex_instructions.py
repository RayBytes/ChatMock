"""Test that gpt-5-codex picks codex instructions via app config."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_codex_model_uses_codex_instructions(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["GPT5_CODEX_INSTRUCTIONS"] = "CODEX_INSTR"
    seen = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        seen.update(kw)

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {"model": "gpt-5-codex", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert seen.get("instructions") == "CODEX_INSTR"
