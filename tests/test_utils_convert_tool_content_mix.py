"""Cover both text/content branches in tool output aggregation."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_tool_role_aggregates_text_and_content() -> None:
    msgs = [
        {
            "role": "tool",
            "tool_call_id": "abc",
            "content": [{"content": "A"}, {"text": "B"}],
        }
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out and out[0]["type"] == "function_call_output" and out[0]["output"] == "A\nB"
