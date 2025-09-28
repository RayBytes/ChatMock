"""Test sse_translate_text path for output_text.done then completed."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {"type": "response.output_text.done"}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_text_done_then_completed_outputs_done_marker() -> None:
    out = b"".join(sse_translate_text(_Up(), "gpt-5", 1))
    assert b'"finish_reason": "stop"' in out and b"data: [DONE]" in out
