"""Documented behavior: response.output_text.done is ignored as generic .done."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield (
            b'data: {"type": "response.output_text.delta", "delta": "Hi", "response": {"id": "r"}}'
        )
        # output_text.done is currently treated as a generic .done and ignored
        yield b'data: {"type": "response.output_text.done", "response": {"id": "r"}}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_chat_output_text_done_is_ignored() -> None:
    out = b"".join(sse_translate_chat(_Up(), "gpt-5", 1))
    # No explicit stop chunk is emitted for output_text.done (covered by generic .done)
    assert b'"finish_reason": "stop"' not in out and b"data: [DONE]" in out
