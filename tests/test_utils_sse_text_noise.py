"""Noise handling for sse_translate_text."""

from __future__ import annotations

from chatmock.utils import sse_translate_text


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b"noise"
        yield b"data: "
        yield b"data: not-json"
        yield b'data: {"type": "response.output_text.delta", "delta": "X", "response": {"id": "r"}}'
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_text_ignores_noise_and_emits_done() -> None:
    out = b"".join(sse_translate_text(_Up(), "m", 1))
    s = out.decode()
    assert "text_completion.chunk" in s and "data: [DONE]" in s
