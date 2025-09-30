"""Extra coverage tests for utils and SSE translators."""

from __future__ import annotations

import json
from pathlib import Path

from chatmock import utils


def test_convert_tool_role_string_content() -> None:
    msgs = [{"role": "tool", "tool_call_id": "c1", "content": "out"}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    assert out
    assert out[0]["type"] == "function_call_output"
    assert out[0]["output"] == "out"


def test_convert_image_url_string_direct() -> None:
    msgs = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": "http://a/b.png"}],
        }
    ]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    assert isinstance(url, str)
    assert url.startswith("http://a/")


def test_convert_assistant_content_output_text() -> None:
    msgs = [{"role": "assistant", "content": "hi"}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    assert out
    assert out[0]["content"][0]["type"] == "output_text"


def test_image_data_url_invalid_is_safely_normalized() -> None:
    # Even with invalid characters, helper normalizes characters and padding
    bad = "data:image/png;base64,@@not-valid@@"
    msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": bad}}]}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    assert isinstance(url, str)
    assert url.startswith("data:image/png;base64,")
    assert len(url.split(",", 1)[1]) % 4 == 0


def test_write_auth_file_success(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CHATGPT_LOCAL_HOME", str(tmp_path / "home"))
    ok = utils.write_auth_file({"tokens": {"a": 1}})
    assert ok is True
    assert (tmp_path / "home" / "auth.json").exists()


class _Up:
    def __init__(self, lines: list[bytes]) -> None:  # type: ignore[no-untyped-def]
        self._lines = lines
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        self.closed = True


def test_sse_chat_reasoning_else_branch_legacy_with_full_text() -> None:
    ev = [
        {"type": "response.reasoning_text.delta", "delta": "R", "response": {"id": "r"}},
        {"type": "response.completed", "response": {}},
    ]
    up = _Up([f"data: {json.dumps(e)}".encode() for e in ev])
    out = b"".join(utils.sse_translate_chat(up, "gpt-5", 1, reasoning_compat="legacy"))
    assert b'"reasoning": "R"' in out


def test_sse_chat_verbose_vlog_called() -> None:
    logs: list[str] = []
    lines = [b"noise", b'data: {"type": "response.completed", "response": {}}']
    up = _Up(lines)
    _ = b"".join(
        utils.sse_translate_chat(
            up,
            "gpt-5",
            1,
            verbose=True,
            vlog=lambda _s: logs.append(_s),  # type: ignore[no-redef]
        )
    )
    assert any("noise" in s for s in logs)
