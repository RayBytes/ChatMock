"""Force ValueError in json.dumps during function_call args serialization."""

from __future__ import annotations

import json

import pytest

from chatmock import utils


class _Up:
    def __init__(self, events: list[dict]) -> None:  # type: ignore[no-untyped-def]
        # Pre-encode before monkeypatching json.dumps
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_output_item_done_args_dump_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    ev = [
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "c1", "name": "fn", "arguments": {"a": 1}},
            "response": {"id": "r"},
        },
        {"type": "response.completed", "response": {}},
    ]
    up = _Up(ev)

    _orig = utils.json.dumps

    def _boom(obj, *a, **k):  # type: ignore[no-untyped-def]
        if isinstance(obj, dict) and set(obj.keys()) == {"a"}:  # match arguments dict shape
            raise ValueError("x")
        return _orig(obj, *a, **k)

    monkeypatch.setattr(utils.json, "dumps", _boom, raising=True)
    out = b"".join(utils.sse_translate_chat(up, "gpt-5", 1))
    assert b"data: [DONE]" in out
