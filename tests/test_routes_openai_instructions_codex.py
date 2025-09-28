"""Cover codex instructions selection in OpenAI chat route."""

from __future__ import annotations

import json
from typing import Any

import pytest

import chatmock.routes_openai as routes


def test_openai_codex_instructions_selected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = {}

    def fake_start(model: str, input_items: list[dict[str, Any]], **kw: Any):
        seen.update(kw)

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    # Set custom codex instructions and request the codex model
    client.application.config["GPT5_CODEX_INSTRUCTIONS"] = "CODEX"
    body = {"model": "gpt-5-codex", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200 and seen.get("instructions") == "CODEX"


def test_openai_codex_instructions_blank_uses_base(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = {}

    def fake_start(model: str, input_items: list[dict[str, Any]], **kw: Any):
        seen.update(kw)

        class _U:
            status_code = 200

            def iter_lines(self, decode_unicode: bool = False):
                yield b'data: {"type": "response.completed", "response": {}}'

            def close(self):
                return None

        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    # Set base and blank codex; should fall back to BASE
    client.application.config["BASE_INSTRUCTIONS"] = "BASE"
    client.application.config["GPT5_CODEX_INSTRUCTIONS"] = "  "
    body = {"model": "gpt-5-codex", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200 and seen.get("instructions") == "BASE"
