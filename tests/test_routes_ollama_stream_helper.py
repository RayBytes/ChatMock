"""Directly exercise Ollama stream generator to raise coverage."""

from __future__ import annotations

import json

import chatmock.routes_ollama as routes


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_ollama_stream_helper_think_tags_branches() -> None:
    events = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S1"},
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S2"},
        {"type": "response.output_text.delta", "delta": "Hi"},
        {"type": "response.completed", "response": {}},
    ]
    gen = routes._ollama_stream_gen(_Up(events), "gpt-5", "2023-01-01T00:00:00Z", "think-tags")
    out = "".join(gen)
    # Expect think tags open/close and final done object
    assert "<think>" in out and "</think>" in out and '"done": true' in out.lower()
