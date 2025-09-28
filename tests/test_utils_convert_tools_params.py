"""Cover convert_tools_chat_to_responses when parameters missing or wrong type."""

from __future__ import annotations

from chatmock.utils import convert_tools_chat_to_responses


def test_convert_tools_params_defaults_and_description() -> None:
    tools = [
        {"type": "function", "function": {"name": "x", "description": "d", "parameters": None}},
        {"type": "function", "function": {"name": "y"}},
    ]
    out = convert_tools_chat_to_responses(tools)
    assert out[0]["parameters"]["type"] == "object" and out[1]["description"] == ""
