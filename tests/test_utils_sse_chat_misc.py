"""Misc branches for sse_translate_chat."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {"type": "custom.done", "response": {"id": "r"}}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_chat_ignores_generic_done() -> None:
    out = b"".join(sse_translate_chat(_Up(), "m", 1))
    assert b"data: [DONE]" in out
