"""Test sse_translate_text include_usage branch."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        del decode_unicode
        yield (
            b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 1, '
            b'"output_tokens": 2, "total_tokens": 3}}}'
        )

    def close(self) -> None:
        return None


def test_sse_text_include_usage_emits_chunk() -> None:
    """Include usage chunk in text path then final [DONE]."""
    out = b"".join(sse_translate_text(_Up(), "gpt-5", 1, include_usage=True))
    assert b'"usage": {' in out
    assert b"data: [DONE]" in out
