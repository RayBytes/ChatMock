"""Tests for SSE translation to text completion chunks."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_text


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events] + [b"data: [DONE]"]
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        del decode_unicode
        yield from self._lines

    def close(self) -> None:
        self.closed = True


def test_sse_translate_text_emits_chunks_and_done() -> None:
    """Translate SSE to text chunks, include usage and final [DONE]."""
    events = [
        {"type": "response.output_text.delta", "delta": "Hi", "response": {"id": "r1"}},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        },
    ]
    up = _Up(events)
    out = b"".join(sse_translate_text(up, "gpt-5", 1, include_usage=True))
    s = out.decode()
    assert "text_completion.chunk" in s
    assert "data: [DONE]" in s
    assert "usage" in s
