"""Cover codex instructions edge case: non-string config value."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_openai_codex_instructions_nonstring_uses_base(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When GPT5_CODEX_INSTRUCTIONS is not a string, fall back to base."""
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
    # Set base and non-string codex config; should fall back to BASE
    client.application.config["BASE_INSTRUCTIONS"] = "BASE"
    client.application.config["GPT5_CODEX_INSTRUCTIONS"] = ["not", "a", "string"]
    body = {
        "model": "gpt-5-codex",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert seen.get("instructions") == "BASE"
