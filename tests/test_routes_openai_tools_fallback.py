"""Tests for OpenAI chat route tools rejection fallback behavior."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_completions_tools_rejected_returns_error(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Bad:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    calls = {"n": 0}

    def fake_start(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return _Bad(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert (
        resp.status_code == 400 and resp.get_json()["error"]["code"] == "RESPONSES_TOOLS_REJECTED"
    )
