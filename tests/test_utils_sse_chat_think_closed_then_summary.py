"""Exercise think-tags branch where think is already closed when summary arrives."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events) -> None:
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self):
        return None


def test_think_closed_then_summary_no_output_but_done() -> None:
    ev = [
        {"type": "response.reasoning_summary_part.added", "response": {"id": "r"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "S", "response": {"id": "r"}},
        {
            "type": "response.output_text.delta",
            "delta": "x",
            "response": {"id": "r"},
        },  # closes think
        {"type": "response.reasoning_summary_text.delta", "delta": "T", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1, reasoning_compat="think-tags"))
    s = out.decode()
    assert "</think>" in s
    assert "data: [DONE]" in s
