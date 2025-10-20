"""Force exception paths inside sse_translate_chat web_search block."""

from __future__ import annotations

import json

from chatmock import utils


class _Up:
    def __init__(self, lines: list[bytes]) -> None:  # type: ignore[no-untyped-def]
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_web_search_inner_try_except_swallowed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Prepare JSON-encoded events first (using stdlib json)
    raw_events = [
        {"type": "web_search_call.delta", "item_id": "w", "item": {"parameters": {"q": "hello"}}},
        {"type": "web_search_call.completed", "item_id": "w"},
        {"type": "response.completed", "response": {}},
    ]
    lines = [f"data: {json.dumps(e)}".encode() for e in raw_events]
    up = _Up(lines)

    # Arrange: make json.dumps raise inside the web_search try-block
    def _boom(*a, **k):  # type: ignore[no-untyped-def]
        msg = "x"
        raise ValueError(msg)

    monkeypatch.setattr(utils.json, "dumps", _boom, raising=True)

    out = b"".join(utils.sse_translate_chat(up, "m", 1))
    # Even with exceptions inside the web_search block, translation should finish cleanly
    assert b"data: [DONE]" in out
