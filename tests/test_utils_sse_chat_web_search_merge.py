"""Exercise merging of web_search parameters across events in sse_translate_chat."""

from __future__ import annotations

import json

from chatmock.utils import sse_translate_chat


class _Up:
    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        del decode_unicode
        yield from self._lines

    def close(self) -> None:
        return None


def test_web_search_merge_params_and_finish() -> None:
    """Merges web_search parameters across events and finishes cleanly."""
    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "ws2",
            "item": {
                "parameters": {"q": "q1", "domains": ["a.example"]},
                "recency": "week",
                "max_results": 5,
            },
        },
        {
            "type": "web_search_call.delta",
            "item_id": "ws2",
            "item": {"include_domains": ["b.example"], "topn": 3, "days": 2},
        },
        {"type": "web_search_call.completed", "item_id": "ws2"},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode().replace(" ", "")
    assert '"tool_calls"' in s
