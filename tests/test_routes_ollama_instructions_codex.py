"""Cover codex instructions selection in Ollama route."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_ollama as routes


def test_ollama_codex_instructions_selected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    client.application.config["GPT5_CODEX_INSTRUCTIONS"] = "CODEX"
    body = {"model": "gpt-5-codex", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200 and seen.get("instructions") == "CODEX"
