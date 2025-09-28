"""Ensure Text Completions builds input_items from prompt when messages not provided."""

from __future__ import annotations

import json
from typing import Any

import pytest

import chatmock.routes_openai as routes


def test_completions_uses_prompt_when_no_messages(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    def fake_start(model: str, input_items: list[dict[str, Any]], **kw: Any):
        seen["input_items"] = input_items
        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {"model": "gpt-5", "prompt": "hello"}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 200 and seen["input_items"][0]["content"][0]["text"] == "hello"
