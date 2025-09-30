"""Extra route and transform tests to cover missed branches."""

from __future__ import annotations

import json

from chatmock.transform import convert_ollama_messages
from chatmock.utils import sse_translate_chat, sse_translate_text


def test_openai_models_expose_variants(client: object) -> None:
    client.application.config["EXPOSE_REASONING_MODELS"] = True
    r = client.get("/v1/models")
    data = r.get_json()
    ids = [m["id"] for m in data["data"]]
    assert r.status_code == 200
    assert "gpt-5-high" in ids
    assert "gpt-5-codex-low" in ids


def test_ollama_tags_expose_variants(client: object) -> None:
    client.application.config["EXPOSE_REASONING_MODELS"] = True
    r = client.get("/api/tags")
    data = r.get_json()
    names = [m["name"] for m in data["models"]]
    assert r.status_code == 200
    assert "gpt-5-high" in names
    assert "gpt-5-codex-low" in names


def test_transform_tool_role_with_string_content() -> None:
    msgs = [{"role": "tool", "id": "c1", "content": "OUT"}]
    out = convert_ollama_messages(msgs, None)
    tool = out[0]
    assert tool.get("role") == "tool"
    assert tool.get("content")[0]["text"] == "OUT"


class _UpStr:
    def __init__(self, lines) -> None:  # type: ignore[no-untyped-def]
        self._lines = lines
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        self.closed = True


def test_sse_text_accepts_str_lines() -> None:
    lines = [
        'data: {"type": "response.output_text.delta", "delta": "x", "response": {"id": "r"}}',
        'data: {"type": "response.completed", "response": {}}',
    ]
    up = _UpStr(lines)
    out = b"".join(sse_translate_text(up, "m", 1))
    assert b"text_completion.chunk" in out


def test_sse_chat_generic_done_is_ignored() -> None:
    # Exercise the generic ".done" branch that is not specific to output_text
    events = [
        {"type": "something.custom.done", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    up = _UpStr([f"data: {json.dumps(e)}" for e in events])
    out = b"".join(sse_translate_chat(up, "m", 1))
    assert b"data: [DONE]" in out
