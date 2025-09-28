"""Cover include_usage=True path in sse_translate_text."""

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


def test_text_stream_includes_usage_before_done() -> None:
    ev = [
        {"type": "response.output_text.delta", "delta": "hello"},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2}},
        },
    ]
    out = b"".join(sse_translate_text(_U(ev), "gpt-5", 1, include_usage=True))
    s = out.decode().replace(" ", "")
    assert '"usage":' in s and "data:[DONE]" in s
