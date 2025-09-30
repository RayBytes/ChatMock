"""Cover summary_part.added when compat is unknown (branch false)."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _U:
    def __init__(self, events) -> None:
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self):
        return None


def test_summary_added_unknown_compat_no_effect() -> None:
    ev = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_U(ev), "gpt-5", 1, reasoning_compat="unknown"))
    assert b"data: [DONE]" in out
