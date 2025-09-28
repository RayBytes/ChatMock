"""Edge case tests for conversion helpers in utils."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input, convert_tools_chat_to_responses


def test_convert_chat_messages_tool_role_list_content() -> None:
    msgs = [{"role": "tool", "tool_call_id": "c1", "content": [{"text": "a"}, {"content": "b"}]}]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out and out[0]["type"] == "function_call_output" and out[0]["output"] == "a\nb"


def test_convert_chat_messages_ignores_unknown_ptype() -> None:
    msgs = [{"role": "user", "content": [{"type": "unknown", "text": "x"}]}]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out == []


def test_convert_tools_chat_ignores_non_function_and_missing_name() -> None:
    tools = [{"type": "notfunc"}, {"type": "function", "function": {}}]
    out = convert_tools_chat_to_responses(tools)
    assert out == []
