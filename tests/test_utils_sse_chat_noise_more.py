"""Extra noise branches for sse_translate_chat: empty raw/data and early DONE."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b""  # empty raw -> continue
        yield b"data: "  # empty data -> continue
        yield b"data: [DONE]"  # break

    def close(self) -> None:
        return None


def test_sse_chat_empty_and_done_paths() -> None:
    out = b"".join(sse_translate_chat(_Up(), "m", 1))
    # With only early [DONE] and no events, translator breaks without emitting
    assert out == b""
