"""Cover non-dict content parts in convert_chat_messages_to_responses_input."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_convert_ignores_nondict_content_parts() -> None:
    msgs = [{"role": "user", "content": ["bad", {"type": "text", "text": "ok"}]}]
    out = convert_chat_messages_to_responses_input(msgs)  # type: ignore[arg-type]
    assert out and out[0]["content"][0]["text"] == "ok"
