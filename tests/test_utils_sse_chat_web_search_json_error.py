"""Force json.dumps error in sse_translate_chat web_search args to hit fallback."""

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


def test_web_search_args_json_error_falls_back_to_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    orig_dumps = utils.json.dumps  # type: ignore[attr-defined]

    def fake_dumps(obj, *a, **k):  # type: ignore[no-untyped-def]
        if isinstance(obj, dict) and obj.get("a") == 1:
            raise TypeError("boom")
        return orig_dumps(obj, *a, **k)

    monkeypatch.setattr(utils.json, "dumps", fake_dumps)

    ev = [
        {
            "type": "web_search_call.delta",
            "item_id": "wsx",
            "item": {"parameters": {"a": 1}},
            "response": {"id": "r"},
        },
        {"type": "web_search_call.done", "item_id": "wsx", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(utils.sse_translate_chat(_Up(ev), "gpt-5", 1))
    s = out.decode().replace(" ", "")
    assert '"arguments":"{}"' in s and "data: [DONE]" in out.decode()
