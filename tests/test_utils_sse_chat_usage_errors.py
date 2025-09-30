"""Exercise _extract_usage error path in sse_translate_chat."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        # usage values cause int() to raise -> except path returns None
        yield (
            b'data: {"type": "response.completed", '
            b'"response": {"usage": {"input_tokens": "NaN"}}}'
        )

    def close(self) -> None:
        return None


def test_sse_chat_usage_value_error_handled() -> None:
    out = b"".join(sse_translate_chat(_Up(), "gpt-5", 1, include_usage=True))
    # Still completes; usage chunk may be suppressed due to error
    assert b"data: [DONE]" in out
