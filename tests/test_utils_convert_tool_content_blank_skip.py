"""Cover tool content aggregator skipping blank parts."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_tool_content_skips_blank_parts() -> None:
    msgs = [
        {
            "role": "tool",
            "tool_call_id": "abc",
            "content": [{"text": ""}, {"content": "X"}],
        }
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out and out[0]["output"] == "X"
