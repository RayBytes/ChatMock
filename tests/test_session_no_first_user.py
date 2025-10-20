"""Session canonicalization when no first user message exists."""

from __future__ import annotations

from chatmock.session import canonicalize_prefix


def test_canonicalize_prefix_no_first_user_only_instructions() -> None:
    js = canonicalize_prefix(
        "Only",
        [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "X"}],
            }
        ],
    )
    assert js.startswith('{"instructions":"Only"')
