"""Force json.dumps error in sse_translate_chat output_item.done args handling."""

from __future__ import annotations

import json as _json

from chatmock import utils


class _Up:
    def __init__(self, events):  # type: ignore[no-untyped-def]
        self._lines = [f"data: {_json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_output_item_args_json_error_falls_back(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    orig_dumps = utils.json.dumps  # type: ignore[attr-defined]

    def fake_dumps(obj, *a, **k):  # type: ignore[no-untyped-def]
        if isinstance(obj, dict) and obj.get("z") == 9:
            raise TypeError("boom")
        return orig_dumps(obj, *a, **k)

    monkeypatch.setattr(utils.json, "dumps", fake_dumps)

    ev = [
        {
            "type": "response.output_item.done",
            "item": {"type": "function_call", "id": "c1", "name": "fn", "parameters": {"z": 9}},
            "response": {"id": "r1"},
        },
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(utils.sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode().replace(" ", "")
    assert '"arguments":"{}"' in s
