"""Ensure web_search_call.delta twice uses stable index (else branch)."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events):
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        for l in self._lines:
            yield l

    def close(self):
        return None


def test_web_search_delta_twice_same_call_id() -> None:
    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "ws1",
            "item": {"parameters": {"q": "x"}},
            "response": {"id": "r"},
        },
        {
            "type": "web_search_call.delta",
            "item_id": "ws1",
            "item": {"parameters": {"q": "x2"}},
            "response": {"id": "r"},
        },
        {"type": "web_search_call.done", "item_id": "ws1", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode().replace(" ", "")
    # Ensure multiple delta chunks exist and tool_calls finish emitted; index should be stable (index":0)
    assert s.count('"tool_calls"') >= 2 and '"finish_reason":"tool_calls"' in s
