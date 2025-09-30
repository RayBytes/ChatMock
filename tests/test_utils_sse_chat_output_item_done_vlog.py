"""Cover vlog path inside response.output_item.done web_search_call."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events) -> None:
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self):
        return None


def test_output_item_done_vlog_and_finish_chunk() -> None:
    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "ws1",
            "item": {"parameters": {"q": "x"}},
            "response": {"id": "r"},
        },
        {
            "type": "response.output_item.done",
            "item": {
                "type": "web_search_call",
                "id": "ws1",
                "name": "web_search",
                "arguments": {"q": "x"},
            },
            "response": {"id": "r"},
        },
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 2}},
        },
    ]
    logs: list[str] = []

    def vlog(line: str) -> None:
        logs.append(line)

    out = b"".join(
        sse_translate_chat(_Up(ev), "gpt-5", 1, verbose=True, vlog=vlog, include_usage=True)
    )
    s = out.decode().replace(" ", "")
    assert any("response.output_item.done web_search_call" in log_line for log_line in logs)
    assert '"finish_reason":"tool_calls"' in s
    assert '"usage":' in s
    assert "data: [DONE]" in out.decode()
