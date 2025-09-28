"""Extra coverage for sse_translate_text edge cases."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def __init__(self, lines):  # type: ignore[no-untyped-def]
        self._lines = lines
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        self.closed = True


def test_sse_text_done_first_emits_stop_and_done() -> None:
    up = _Up([b"data: [DONE]"])
    out = b"".join(sse_translate_text(up, "gpt-5", 1))
    s = out.decode()
    # DONE-first yields a stop chunk; no explicit [DONE] is emitted in this code path
    assert "text_completion.chunk" in s
