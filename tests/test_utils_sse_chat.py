"""Tests for SSE translation for chat completion chunks."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        self.closed = True


def test_sse_translate_chat_tool_calls_and_usage() -> None:
    events = [
        {
            "type": "web_search_call.delta",
            "item_id": "ws1",
            "item": {"parameters": {"q": "x"}},
            "response": {"id": "r1"},
        },
        {"type": "web_search_call.completed", "item_id": "ws1", "response": {"id": "r1"}},
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "c1", "name": "fn", "arguments": {"a": 1}},
            "response": {"id": "r1"},
        },
        {"type": "response.reasoning_summary_part.added", "response": {"id": "r1"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "sum", "response": {"id": "r1"}},
        {"type": "response.reasoning_text.delta", "delta": "full", "response": {"id": "r1"}},
        {"type": "response.output_text.delta", "delta": "Hello", "response": {"id": "r1"}},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        },
    ]
    up = _Up(events)
    out = b"".join(
        sse_translate_chat(up, "gpt-5", 1, reasoning_compat="think-tags", include_usage=True)
    )
    s = out.decode()
    assert '"tool_calls"' in s
    assert "<think>" in s
    assert "Hello" in s
    assert "data: [DONE]" in s
