"""Force json dump error for usage chunk to cover suppressed exception path."""

from __future__ import annotations

import pytest

from chatmock import utils


class _U:
    def iter_lines(self, decode_unicode: bool = False):
        yield b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 1, "output_tokens": 2}}}'

    def close(self):
        return None


def test_text_usage_chunk_json_error_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    orig = utils.json.dumps

    def boom(obj, *a, **k):
        if (
            isinstance(obj, dict)
            and obj.get("object") == "text_completion.chunk"
            and "usage" in obj
        ):
            raise ValueError("boom")
        return orig(obj, *a, **k)

    monkeypatch.setattr(utils.json, "dumps", boom, raising=True)
    out = b"".join(utils.sse_translate_text(_U(), "gpt-5", 1, include_usage=True))
    assert b"data: [DONE]" in out
