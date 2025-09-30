"""Ensure DEFAULT_WEB_SEARCH does not inject when responses_tool_choice='none'."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_openai_default_web_search_not_injected_when_none(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["DEFAULT_WEB_SEARCH"] = True
    captured: dict[str, Any] = {}

    def fake_start(model: str, input_items: list[dict[str, Any]], **kw: Any):
        captured.update(kw)

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
        "messages": [],
        "responses_tool_choice": "none",
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    tools = captured.get("tools") or []
    assert resp.status_code == 200
    assert not any(t.get("type") == "web_search" for t in tools)
