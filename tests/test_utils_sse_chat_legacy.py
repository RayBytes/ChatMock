"""Test sse_translate_chat legacy/current reasoning fields in delta."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield (
            b'data: {"type": "response.reasoning_summary_text.delta", '
            b'"delta": "S", "response": {"id": "r"}}'
        )
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_chat_legacy_reasoning_summary_fields() -> None:
    out = b"".join(sse_translate_chat(_Up(), "m", 1, reasoning_compat="legacy"))
    assert b"reasoning_summary" in out
    assert b"reasoning" in out
    assert b"data: [DONE]" in out
