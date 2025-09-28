"""Exercise web_search call output_item.done branch in sse_translate_chat."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_web_search_output_item_done_emits_tool_calls() -> None:
    ev = [
        {
            "type": "response.output_item.done",
            "item": {"type": "web_search_call", "id": "ws1", "parameters": {"query": "x"}},
            "response": {"id": "r1"},
        },
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1, verbose=True, vlog=lambda s: None))
    s = out.decode()
    # Validate tool_calls appear and the finish reason is set to tool_calls on the same event stream
    assert "tool_calls" in s and '"finish_reason": "tool_calls"'.replace(" ", "") in s.replace(
        " ", ""
    )
