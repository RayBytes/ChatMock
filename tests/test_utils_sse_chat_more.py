"""More branch coverage for sse_translate_chat."""

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


def test_sse_chat_think_tags_newline_and_stop() -> None:
    ev = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S1"},
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S2"},
        {"type": "response.output_text.done"},
        {"type": "response.completed", "response": {}},
    ]
    up = _Up(ev)
    out = b"".join(sse_translate_chat(up, "gpt-5", 1, reasoning_compat="think-tags"))
    s = out.decode()
    assert "\n" in s and "data: [DONE]" in s


def test_sse_chat_failed_emits_error_chunk() -> None:
    ev = [{"type": "response.failed", "response": {"error": {"message": "err"}}}]
    up = _Up(ev)
    out = b"".join(sse_translate_chat(up, "gpt-5", 1))
    assert b'"error": {"message": "err"}' in out
