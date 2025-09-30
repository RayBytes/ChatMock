"""Tests for chatmock.transform Ollama conversions."""

from __future__ import annotations

from chatmock.transform import convert_ollama_messages, normalize_ollama_tools


def test_convert_ollama_messages_basic_and_tool_outputs() -> None:
    msgs = [
        {"role": "user", "content": "hi", "images": ["/9j/AAAA"]},  # jpeg marker
        {
            "role": "assistant",
            "tool_calls": [
                {"function": {"name": "f", "arguments": {"a": 1}}},
            ],
        },
        {"role": "tool", "id": "c1", "content": "ok"},
    ]
    out = convert_ollama_messages(msgs, top_images=["iVBORw0KGgoAAAA"])  # png marker
    # Expect user message with text and images converted to data URLs
    assert any(p.get("type") == "image_url" for p in out[0].get("content", []))
    # Assistant tool call should be present with JSON arguments
    assert out[1]["tool_calls"][0]["function"]["name"] == "f"
    # top_images should be attached to the most recent user message
    user_msgs = [m for m in out if m.get("role") == "user"]
    assert user_msgs
    assert any(
        any(
            p.get("type") == "image_url"
            and isinstance(p.get("image_url", {}).get("url"), str)
            and p["image_url"]["url"].startswith("data:image/png")
            for p in m.get("content", [])
        )
        for m in user_msgs
    )


def test_normalize_ollama_tools_variants() -> None:
    tools = [
        {"function": {"name": "a", "description": "d", "parameters": {"type": "object"}}},
        {"name": "b"},
        {"function": {"name": ""}},
    ]
    out = normalize_ollama_tools(tools)
    names = [t["function"]["name"] for t in out]
    assert names[:2] == ["a", "b"]


def test_convert_ollama_messages_tool_output_links_call_id() -> None:
    # When assistant tool_calls missing id, tool output should backfill the generated id
    msgs = [
        {"role": "assistant", "tool_calls": [{"function": {"name": "f", "arguments": {}}}]},
        {"role": "tool", "content": "ok"},
    ]
    out = convert_ollama_messages(msgs, top_images=None)
    # tool message should have tool_call_id derived from generated call
    tool_msg = next(m for m in out if m.get("role") == "tool")
    assert isinstance(tool_msg.get("tool_call_id"), str)
    assert tool_msg["tool_call_id"]
