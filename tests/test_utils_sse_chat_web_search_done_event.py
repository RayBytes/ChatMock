"""Cover web_search_call.done path in sse_translate_chat, emitting finish chunk."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_web_search_call_done_emits_finish_chunk() -> None:
    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "wsx",
            "item": {"parameters": {"q": "x"}},
            "response": {"id": "r"},
        },
        {"type": "web_search_call.done", "item_id": "wsx", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode().replace(" ", "")
    assert '"finish_reason":"tool_calls"' in s
    assert "data: [DONE]" in out.decode()
