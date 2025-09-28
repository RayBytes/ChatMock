"""Exercise both branches of reasoning_summary_part.added tracking."""

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


def test_summary_added_twice_sets_pending_and_outputs() -> None:
    ev = [
        {"type": "response.reasoning_summary_part.added", "response": {"id": "r"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "A", "response": {"id": "r"}},
        {"type": "response.reasoning_summary_part.added", "response": {"id": "r"}},
        {"type": "response.reasoning_summary_text.delta", "delta": "B", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1, reasoning_compat="think-tags"))
    s = out.decode()
    assert "<think>" in s and "A" in s and "B" in s and "</think>" in s
