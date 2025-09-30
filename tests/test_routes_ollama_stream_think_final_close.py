"""Cover think-tags final close in _ollama_stream_gen when no output_text after think."""

from __future__ import annotations

import json

import chatmock.routes_ollama as routes


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_think_tags_final_close_emitted() -> None:
    events = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.completed", "response": {}},
    ]
    gen = routes._ollama_stream_gen(_Up(events), "gpt-5", "2023-01-01T00:00:00Z", "think-tags")
    out = "".join(gen)
    assert "</think>" in out
    assert '"done": true' in out.lower()
