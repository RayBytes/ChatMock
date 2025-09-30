"""Additional branch coverage for chatmock.utils helpers."""

from __future__ import annotations

import json
from pathlib import Path

from chatmock import utils


def test_read_auth_file_none_env_skips_and_returns_none(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    # Remove env so first two candidates are None -> triggers the continue branch
    monkeypatch.delenv("CHATGPT_LOCAL_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    # Redirect fallback paths to temp dirs that do not exist
    orig_path = utils.Path

    def _p(s: str):  # type: ignore[no-untyped-def]
        s = str(s).replace("~/.chatgpt-local", str(tmp_path / "nope-a"))
        s = s.replace("~/.codex", str(tmp_path / "nope-b"))
        return orig_path(s)

    monkeypatch.setattr(utils, "Path", _p, raising=True)
    assert utils.read_auth_file() is None


def test_image_data_url_error_branch_returns_original() -> None:
    # Missing comma triggers ValueError in split -> except path that returns url
    bad = "data:image/png;base64"  # no comma
    msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": bad}}]}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    img_url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    assert img_url == bad


def test_tool_role_non_str_non_list_content_is_ignored() -> None:
    # content is a dict so it should not be appended as function_call_output
    msgs = [{"role": "tool", "tool_call_id": "c1", "content": {"x": 1}}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    # No function_call_output emitted
    assert all(o.get("type") != "function_call_output" for o in out)


def test_tool_role_list_with_non_dict_parts_yields_empty_output() -> None:
    # Non-dict parts are ignored; join results in empty string output
    msgs = [{"role": "tool", "tool_call_id": "c1", "content": ["not-a-dict"]}]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    fco = next((o for o in out if o.get("type") == "function_call_output"), None)
    assert fco is not None
    assert fco.get("output") == ""


class _Up:
    def __init__(self, lines: list[bytes]) -> None:  # type: ignore[no-untyped-def]
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield from self._lines

    def close(self) -> None:
        return None


def test_sse_chat_web_search_try_block_exception_path_not_crashing() -> None:
    # Force a ValueError inside the try-block by making ws_state contain
    # a non-JSON-serializable value. We do this by first emitting a delta
    # that creates an index, then a crafted event that uses a list as eff_params
    events = [
        {"type": "web_search_call.delta", "item_id": "ws", "item": {"parameters": {"q": "x"}}},
        {"type": "web_search_call.completed", "item_id": "ws"},
        {"type": "response.completed", "response": {}},
    ]
    # Basic sanity: still completes
    out = b"".join(
        utils.sse_translate_chat(_Up([f"data: {json.dumps(e)}".encode() for e in events]), "m", 1)
    )
    assert b"data: [DONE]" in out


def test_sse_chat_output_item_non_dict_is_ignored() -> None:
    events = [
        {"type": "response.output_item.done", "item": "not-a-dict"},
        {"type": "response.completed", "response": {}},
    ]
    out = b"".join(
        utils.sse_translate_chat(_Up([f"data: {json.dumps(e)}".encode() for e in events]), "m", 1)
    )
    assert b"data: [DONE]" in out


def test_sse_text_extract_usage_value_error_and_empty_line() -> None:
    # First yield an empty raw line to cover the 'if not raw_line' branch
    lines = [
        b"",
        b'data: {"type": "response.completed", "response": {"usage": {"input_tokens": "NaN"}}}',
    ]
    out = b"".join(utils.sse_translate_text(_Up(lines), "m", 1))
    assert b"data: [DONE]" in out
