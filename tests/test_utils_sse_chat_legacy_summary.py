"""Cover legacy compat path for reasoning_summary delta in sse_translate_chat."""

from __future__ import annotations

import json
from collections.abc import Iterator

from chatmock import utils


class _Up:
    def __init__(self, events: list[dict]):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_sse_chat_legacy_summary_delta_includes_reasoning_summary() -> None:
    ev = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(utils.sse_translate_chat(_Up(ev), "gpt-5", 1, reasoning_compat="legacy"))
    s = out.decode()
    assert '"reasoning_summary": "S"' in s
