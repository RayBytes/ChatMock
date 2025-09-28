"""Cover stream options and tool choice forwarding in OpenAI chat route."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_stream_forwards_include_usage_and_reasoning_compat(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["REASONING_COMPAT"] = "o3"
    seen = {}

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )

    def fake_sse(
        up,
        model,
        created,
        *,
        verbose=False,
        vlog=None,
        reasoning_compat="think-tags",
        include_usage=False,
    ):  # type: ignore[no-untyped-def]
        seen.update(
            {"reasoning_compat": reasoning_compat, "include_usage": include_usage, "model": model}
        )
        return [b"data: [DONE]\n\n"]

    monkeypatch.setattr(routes, "sse_translate_chat", fake_sse, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert (
        resp.status_code == 200
        and seen["include_usage"] is True
        and seen["reasoning_compat"] == "o3"
    )


def test_chat_responses_tool_choice_none_overrides_and_parallel_flag(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self) -> None:
            return None

    def fake_start(model, input_items, **kw):  # type: ignore[no-untyped-def]
        captured.update(kw)
        return _U(), None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tool_choice": "none",
        "parallel_tool_calls": True,
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert (
        resp.status_code == 200
        and captured.get("tool_choice") == "none"
        and captured.get("parallel_tool_calls") is True
    )
