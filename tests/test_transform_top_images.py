"""Cover transform top_images when no user messages exist."""

from __future__ import annotations

from chatmock.transform import convert_ollama_messages


def test_top_images_attaches_new_user_message() -> None:
    out = convert_ollama_messages([], top_images=["/9j/AAAA"])  # jpeg marker
    user = next((m for m in out if m.get("role") == "user"), None)
    assert user is not None
    assert user.get("content")
