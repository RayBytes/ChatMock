"""Noise and invalid JSON handling in SSE chat translator."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self):
        self._lines = [
            b"noise",
            b"data: not-json",
            b'data: {"type": "response.completed", "response": {}}',
        ]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_sse_chat_ignores_noise_and_invalid_json() -> None:
    out = b"".join(sse_translate_chat(_Up(), "gpt-5", 1))
    assert b"data: [DONE]" in out
