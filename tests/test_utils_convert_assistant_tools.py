"""Cover assistant tool_calls conversion path in utils."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_convert_assistant_tool_calls_to_function_call_items() -> None:
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "do", "arguments": '{"a":1}'},
                }
            ],
        }
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    found = [o for o in out if o.get("type") == "function_call"]
    assert found and found[0]["name"] == "do"
