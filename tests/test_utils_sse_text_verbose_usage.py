"""Cover sse_translate_text verbose logging, early [DONE], and usage chunk."""

from __future__ import annotations

from chatmock import utils


class _Up:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_sse_text_verbose_done_then_completed_with_usage() -> None:
    lines = [
        b"data: [DONE]",
        b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}}}',
    ]
    up = _Up(lines)
    logs: list[str] = []
    out = b"".join(
        utils.sse_translate_text(
            up,
            model="gpt-5",
            created=0,
            verbose=True,
            vlog=logs.append,
            include_usage=True,
        )
    )
    s = out.decode()
    # Should include an initial stop chunk (from early [DONE]), then a usage chunk, then final [DONE]
    assert (
        '"finish_reason": "stop"' in s and '"usage": {"prompt_tokens":' in s and "data: [DONE]" in s
    )
    assert logs  # vlog executed
