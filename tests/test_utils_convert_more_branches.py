"""Extra branch coverage for utils message conversion."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_convert_tool_missing_call_id_yields_no_items() -> None:
    msgs = [{"role": "tool", "content": "x"}]  # no tool_call_id or id
    out = convert_chat_messages_to_responses_input(msgs)
    assert out == []


def test_convert_text_part_blank_skips_append() -> None:
    msgs = [{"role": "user", "content": [{"type": "text", "text": ""}]}]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out == []


def test_convert_image_url_part_with_empty_url_skips_append() -> None:
    msgs = [
        {"role": "user", "content": [{"type": "image_url", "image_url": {"url": ""}}]},
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    assert out == []
