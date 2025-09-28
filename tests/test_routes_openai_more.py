"""More route tests to raise coverage for openai routes."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_completions_responses_tool_unsupported(client: object) -> None:
    body = {"model": "gpt-5", "messages": [], "responses_tools": [{"type": "other"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "RESPONSES_TOOL_UNSUPPORTED"


def test_chat_completions_responses_tools_too_large(client: object) -> None:
    big = "x" * 40000
    body = {
        "model": "gpt-5",
        "messages": [],
        "responses_tools": [{"type": "web_search", "big": big}],
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "RESPONSES_TOOLS_TOO_LARGE"


def test_chat_completions_default_web_search_injected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["DEFAULT_WEB_SEARCH"] = True
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
    monkeypatch.setattr(
        routes, "sse_translate_chat", lambda *a, **k: [b"data: [DONE]\n\n"], raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200 and any(
        t.get("type") == "web_search" for t in seen.get("tools", [])
    )


def test_chat_completions_upstream_error_no_tools(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 400 and "bad" in resp.get_json()["error"]["message"]


def test_chat_completions_tools_fallback_on_error(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    class _U1:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    class _U2:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    def fake_start(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (_U1(), None) if calls["n"] == 1 else (_U2(), None)

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    monkeypatch.setattr(
        routes, "sse_translate_chat", lambda *a, **k: [b"data: [DONE]\n\n"], raising=True
    )
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200 and calls["n"] == 2
