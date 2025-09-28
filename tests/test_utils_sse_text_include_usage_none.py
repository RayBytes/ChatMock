"""Cover include_usage True when upstream provides no usage in text SSE."""

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


def test_text_include_usage_flag_without_usage() -> None:
    ev = [
        {"type": "response.output_text.delta", "delta": "x"},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_text(_U(ev), "gpt-5", 1, include_usage=True))
    s = out.decode().replace(" ", "")
    assert '"text":"x"' in s and "data:[DONE]" in s
