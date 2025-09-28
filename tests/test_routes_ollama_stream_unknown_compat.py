"""Cover _ollama_stream_gen with unknown reasoning compat (ignore reasoning deltas)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import chatmock.routes_ollama as routes


class _Up:
    def __init__(self, events: list[dict]):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_stream_unknown_compat_ignores_reasoning_deltas() -> None:
    events = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.output_text.delta", "delta": "Hi"},
        {"type": "response.completed", "response": {}},
    ]
    out = "".join(routes._ollama_stream_gen(_Up(events), "gpt-5", "2023", "unknown"))
    # Should only include the output_text content, not think tags
    assert '"content": "Hi"' in out and "<think>" not in out
