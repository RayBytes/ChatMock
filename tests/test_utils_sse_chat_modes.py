"""Additional mode tests for SSE chat translator."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_sse_chat_o3_mode_includes_reasoning_content() -> None:
    ev = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.reasoning_text.delta", "delta": "F"},
        {"type": "response.completed", "response": {}},
    ]
    up = _Up(ev)
    out = b"".join(sse_translate_chat(up, "gpt-5", 1, reasoning_compat="o3"))
    assert b'"reasoning"' in out


def test_sse_chat_legacy_mode_sets_summary_fields() -> None:
    ev = [
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.completed", "response": {}},
    ]
    up = _Up(ev)
    out = b"".join(sse_translate_chat(up, "gpt-5", 1, reasoning_compat="legacy"))
    assert b"reasoning_summary" in out
    assert b"reasoning" in out
