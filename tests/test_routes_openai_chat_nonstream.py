"""Non-stream Chat Completions tests for OpenAI-compatible route."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_chat_completions_nonstream_aggregates_text_and_tool_calls(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        {"type": "response.output_text.delta", "delta": "Hello", "response": {"id": "r1"}},
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "c1", "name": "sum", "arguments": "{}"},
        },
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        },
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(events), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    data = resp.get_json()
    msg = data["choices"][0]["message"]
    assert msg["content"] == "Hello" and msg.get("tool_calls")
    assert data.get("usage", {}).get("total_tokens") == 3


def test_chat_completions_nonstream_failed_returns_502(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [{"type": "response.failed", "response": {"error": {"message": "oops"}}}]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(events), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 502 and resp.get_json()["error"]["message"] == "oops"
