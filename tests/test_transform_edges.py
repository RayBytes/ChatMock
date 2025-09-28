"""Edge-case coverage for transform functions branches."""

from __future__ import annotations

from chatmock.transform import convert_ollama_messages, normalize_ollama_tools, to_data_url


def test_to_data_url_non_string_and_empty() -> None:
    assert to_data_url(123) == 123  # type: ignore[arg-type]
    assert to_data_url("") == ""


def test_convert_ollama_messages_edge_branches() -> None:
    msgs = [
        123,  # skipped non-dict
        {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "text", "text": 1}]},
        {
            "role": "user",
            "content": ["ignore non-dict entries"],
            "images": [None, "http://x/y.png"],
        },
        {
            "role": "assistant",
            "tool_calls": [
                123,
                {"function": {}},
                {"function": {"name": "f"}, "id": "id1", "call_id": "ignored"},
            ],
        },
        {"role": "tool", "id": "tool1"},
    ]
    out = convert_ollama_messages(msgs, top_images=[None, ""])
    # Ensure entries exist and id was propagated for assistant call
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in out)
    assert any(m.get("role") == "tool" and m.get("tool_call_id") == "tool1" for m in out)


def test_normalize_ollama_tools_non_list_and_invalid_items() -> None:
    assert normalize_ollama_tools(None) == []  # type: ignore[arg-type]
    out = normalize_ollama_tools([123, {"function": {"name": ""}}, {"other": 1}])
    assert out == []
