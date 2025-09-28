"""Cover branch where output_text.delta has empty string (no yield)."""

from __future__ import annotations

import json

import chatmock.routes_ollama as routes


class _Up:
    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_stream_think_tags_empty_output_delta_no_yield() -> None:
    ev = [
        {"type": "response.reasoning_summary_text.delta", "delta": "T"},
        {"type": "response.output_text.delta", "delta": ""},
        {"type": "response.completed", "response": {}},
    ]
    out = "".join(routes._ollama_stream_gen(_Up(ev), "gpt-5", "2023", "think-tags"))
    # Expect think tags present, but no extra delta content beyond tags
    assert "<think>" in out and "</think>" in out
