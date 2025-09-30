"""Additional coverage for sse_translate_chat legacy + vlog branches."""

from __future__ import annotations

import json

from chatmock import utils


class _Up:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def _line(obj: object) -> bytes:
    if isinstance(obj, (bytes, bytearray)):
        return obj  # type: ignore[return-value]
    return f"data: {json.dumps(obj)}".encode()


def test_sse_chat_legacy_reasoning_summary_and_failed_with_vlog() -> None:
    events = [
        {"type": "random.done"},  # exercises endswith('.done') pass branch
        {"type": "response.reasoning_summary_text.delta", "delta": "RS"},
        {"type": "response.failed", "response": {"error": {"message": "oops"}}},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}},
        },
    ]
    up = _Up([_line(e) for e in events])
    logs: list[str] = []
    out = b"".join(
        utils.sse_translate_chat(
            up,
            model="gpt-5",
            created=0,
            verbose=True,
            vlog=logs.append,
            reasoning_compat="legacy",
            include_usage=True,
        )
    )
    s = out.decode()
    assert '"reasoning_summary": "RS"' in s
    assert '"error": {"message": "oops"}' in s
    assert '"usage": {"prompt_tokens":' in s
    assert logs
