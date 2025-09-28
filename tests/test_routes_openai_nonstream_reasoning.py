"""Non-stream reasoning application for OpenAI chat route."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_chat_completions_nonstream_o3_reasoning(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Set app compat to o3 for this request
    client.application.config["REASONING_COMPAT"] = "o3"
    events = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.reasoning_text.delta", "delta": "F"},
        {"type": "response.completed", "response": {}},
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(events), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    msg = resp.get_json()["choices"][0]["message"]
    assert "reasoning" in msg and msg["reasoning"]["content"]
