"""Force json dump error for usage chunk to cover suppressed exception path."""

from __future__ import annotations

import pytest

from chatmock import utils


class _U:
    def iter_lines(self, decode_unicode: bool = False):
        del decode_unicode  # unused in test
        yield (
            b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 1, '
            b'"output_tokens": 2}}}'
        )

    def close(self):
        return None


def test_text_usage_chunk_json_error_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    """json.dumps error on usage chunk should be suppressed."""
    orig = utils.json.dumps

    def boom(obj: object, *a: object, **k: object):
        if (
            isinstance(obj, dict)
            and obj.get("object") == "text_completion.chunk"
            and "usage" in obj
        ):
            err: ValueError = ValueError("boom")
            raise err
        return orig(obj, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(utils.json, "dumps", boom, raising=True)
    out = b"".join(utils.sse_translate_text(_U(), "gpt-5", 1, include_usage=True))
    assert b"data: [DONE]" in out
