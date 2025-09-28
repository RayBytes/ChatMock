"""Hit additional parameter merge branches (q/include) in web_search handling."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_web_search_merge_q_and_include_domains() -> None:
    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "w3",
            "q": "hello",
            "include": ["c.example"],
            "response": {"id": "r"},
        },
        {"type": "web_search_call.done", "item_id": "w3", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode()
    assert '"arguments"' in s and "hello" in s and "c.example" in s
