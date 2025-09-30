"""Test include_usage branch in sse_translate_chat."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self) -> None:
        self._lines = [
            b'data: {"type": "response.completed", "response": {"id": "r", '
            b'"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}}}',
        ]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_sse_chat_include_usage_emits_chunk() -> None:
    out = b"".join(sse_translate_chat(_Up(), "gpt-5", 1, include_usage=True))
    s = out.decode()
    assert '"usage":' in s
    assert "data: [DONE]" in s
