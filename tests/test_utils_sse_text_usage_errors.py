"""Exercise _extract_usage error path in sse_translate_text."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        # usage contains string to trigger ValueError in int()
        yield b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": "bad"}}}'

    def close(self) -> None:
        return None


def test_sse_text_usage_value_error_handled() -> None:
    out = b"".join(sse_translate_text(_Up(), "gpt-5", 1, include_usage=True))
    # Should still emit final [DONE] but no usage chunk
    assert b"data: [DONE]" in out
