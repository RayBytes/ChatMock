"""Cover response.completed without response field in text SSE."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_text


class _U:
    def __init__(self, events):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        for l in self._lines:
            yield l

    def close(self):
        return None


def test_text_completed_without_response_id() -> None:
    ev = [
        {"type": "response.output_text.delta", "delta": "x"},
        {"type": "response.completed"},
    ]
    out = b"".join(sse_translate_text(_U(ev), "gpt-5", 1, include_usage=False))
    assert b"data: [DONE]" in out
