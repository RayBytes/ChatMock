"""Edge cases for assistant tool_calls conversion in utils."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_assistant_tool_calls_ignore_non_dict_and_non_string_args() -> None:
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                123,
                {"type": "function", "function": {"name": "f", "arguments": {"a": 1}}},
            ],
        },
        {"role": "user", "content": "hi"},
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    # No function_call items should be produced due to invalid types
    assert not any(o.get("type") == "function_call" for o in out)
