"""Cover sse_translate_chat branch where web_search args is a string."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_web_search_string_query_arguments() -> None:
    events = [
        {
            "type": "web_search_call.delta",
            "item_id": "w",
            "item": {"query": "hello"},
            "response": {"id": "r"},
        },
        {"type": "web_search_call.completed", "item_id": "w", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(events), "m", 1))
    s = out.decode()
    assert '"arguments"' in s and "hello" in s and "data: [DONE]" in s
