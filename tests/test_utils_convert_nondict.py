"""Cover non-dict entries in convert_tools_chat_to_responses."""

from __future__ import annotations

from chatmock.utils import convert_tools_chat_to_responses


def test_convert_tools_ignores_non_dict_entries() -> None:
    tools = [123, None, {"type": "function", "function": {"name": "ok"}}]
    out = convert_tools_chat_to_responses(tools)  # type: ignore[arg-type]
    names = [t["name"] for t in out]
    assert names == ["ok"]
