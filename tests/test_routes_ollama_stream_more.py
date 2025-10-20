"""Additional coverage for _ollama_stream_gen o3/legacy branches and final close."""

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


def test_stream_think_tags_closes_in_finally_when_no_output_text() -> None:
    # Only reasoning deltas; ensures finalizer emits closing </think>
    events = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "S"},
        {"type": "response.completed", "response": {}},
    ]
    out = "".join(
        routes._ollama_stream_gen(_Up(events), "gpt-5", "2023-01-01T00:00:00Z", "think-tags")
    )
    assert "<think>" in out
    assert "</think>" in out
    assert '"done": true' in out.lower()


def test_stream_o3_inserts_newline_between_summary_paragraphs() -> None:
    events = [
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "A"},
        {"type": "response.reasoning_summary_part.added"},
        {"type": "response.reasoning_summary_text.delta", "delta": "B"},
        {"type": "response.completed", "response": {}},
    ]
    out = "".join(routes._ollama_stream_gen(_Up(events), "gpt-5", "2023-01-01T00:00:00Z", "o3"))
    assert '\\n"' in out or "\\n}" in out or "\\n,\n" in out  # newline yielded between paragraphs


def test_stream_legacy_compat_pass_through() -> None:
    # Legacy mode ignores reasoning deltas in generator (covered by else: pass)
    events = [
        {"type": "response.reasoning_summary_text.delta", "delta": "X"},
        {"type": "response.output_text.delta", "delta": "Hi"},
        {"type": "response.completed", "response": {}},
    ]
    out = "".join(routes._ollama_stream_gen(_Up(events), "gpt-5", "2023-01-01T00:00:00Z", "legacy"))
    assert '"content": "Hi"' in out
    assert '"done": true' in out.lower()
