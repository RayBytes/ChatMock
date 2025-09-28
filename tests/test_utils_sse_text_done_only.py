"""Cover the [DONE] sentinel branch in sse_translate_text."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def iter_lines(self, decode_unicode: bool = False):
        yield b"data: [DONE]"

    def close(self):
        return None


def test_text_done_only_emits_stop_chunk() -> None:
    out = b"".join(sse_translate_text(_Up(), "gpt-5", 1))
    assert b"text_completion.chunk" in out
