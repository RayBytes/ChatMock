"""Cover function_call item with string arguments in sse_translate_chat."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_function_call_output_item_with_string_arguments() -> None:
    ev = [
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "c1",
                "name": "fn",
                "arguments": '{"a":1}',
            },
            "response": {"id": "r"},
        },
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode()
    assert '"tool_calls"' in s and '"name": "fn"' in s
