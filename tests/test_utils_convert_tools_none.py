"""Cover convert_tools_chat_to_responses when tools is not a list."""

from __future__ import annotations

from chatmock.utils import convert_tools_chat_to_responses


def test_convert_tools_none_returns_empty() -> None:
    assert convert_tools_chat_to_responses(None) == []  # type: ignore[arg-type]
