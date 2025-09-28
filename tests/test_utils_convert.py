"""Tests for conversion helpers in chatmock.utils."""

from __future__ import annotations

import json

from chatmock.utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
)


def test_convert_chat_messages_basic_text_and_image() -> None:
    """User text and image entries become input items for Responses API."""
    msgs = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "hello"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "show"},
                {"type": "image_url", "image_url": {"url": "http://x/y.png"}},
            ],
        },
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    # two message items expected
    kinds = [o["type"] for o in out]
    assert kinds.count("message") >= 2
    # ensure one has input_image
    assert any(
        any(p.get("type") == "input_image" for p in o.get("content", []))
        for o in out
        if o.get("type") == "message"
    )


def test_convert_tools_chat_to_responses_function() -> None:
    """Function tools convert to Responses function tool objects."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
            },
        }
    ]
    out = convert_tools_chat_to_responses(tools)
    assert out and out[0]["type"] == "function"
    # round-trip JSON to ensure serializable
    json.dumps(out)
