"""Additional tests for canonicalize_prefix image handling."""

from __future__ import annotations

from chatmock.session import canonicalize_prefix


def test_canonicalize_prefix_includes_image_url() -> None:
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [
                {"type": "input_text", "text": "hello"},
                {"type": "input_image", "image_url": "http://example/x.png"},
            ],
        }
    ]
    js = canonicalize_prefix("instr", items)
    assert "first_user_message" in js and "http://example/x.png" in js
