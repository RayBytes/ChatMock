"""Cover type-check false branch in output_item.done (non-str call_id)."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        for l in self._lines:
            yield l

    def close(self):
        return None


def test_output_item_done_skips_when_call_id_not_str() -> None:
    ev = [
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": 123, "name": "fn", "arguments": "{}"},
            "response": {"id": "r"},
        },
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    # Should only show DONE without tool_calls delta
    assert out.decode().count("tool_calls") == 0 and b"data: [DONE]" in out
