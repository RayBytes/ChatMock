"""Non-stream think-tags reasoning application for OpenAI chat route."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def __init__(self, events: list[dict]):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_chat_completions_nonstream_think_tags_reasoning(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.reasoning_text.delta", "delta": "F"},
        {"type": "response.completed", "response": {}},
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(events), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": ""}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    msg = resp.get_json()["choices"][0]["message"]
    # Default compat is think-tags; ensure reasoning was attached as a <think> block in content
    assert isinstance(msg.get("content"), str) and msg["content"].startswith("<think>")
