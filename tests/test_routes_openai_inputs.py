"""Input shaping tests for OpenAI chat route."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_completions_uses_prompt_when_no_messages(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured["input_items"] = input_items

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

    body = {"model": "gpt-5", "prompt": "hello", "stream": True}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert captured["input_items"][0]["content"][0]["text"] == "hello"


def test_chat_completions_moves_system_to_front(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setattr(
        routes, "sse_translate_chat", lambda *a, **k: [b"data: [DONE]\n\n"], raising=True
    )

    body = {
        "model": "gpt-5",
        "messages": [{"role": "system", "content": "x"}, {"role": "user", "content": "hi"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200 and seen["first_role"] == "user"


def test_chat_completions_prompt_fallback_when_no_valid_items(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured["input_items"] = input_items

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

    body = {
        "model": "gpt-5",
        # Provide a system-only (blank) message so conversion yields []
        "messages": [{"role": "system", "content": ""}],
        # Ensure prompt fallback is used to build input_items
        "prompt": "hello2",
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert captured["input_items"][0]["content"][0]["text"] == "hello2"
