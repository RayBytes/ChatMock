"""Edge-case coverage for session helpers internals."""

from __future__ import annotations

from chatmock import session as ses


def test_canonicalize_first_user_message_skips_invalid_parts() -> None:
    items = [
        123,  # not a dict
        {"type": "other"},
        {"type": "message", "role": "assistant", "content": []},
        {"type": "message", "role": "user", "content": "not-a-list"},
        {
            "type": "message",
            "role": "user",
            "content": [123, {"type": "input_text", "text": ""}, {"type": "input_image"}],
        },
    ]
    # No valid content parts -> first_user_message omitted
    js = ses.canonicalize_prefix("X", items)  # exercises all continue branches
    assert js.startswith('{"instructions":"X"}')
    assert "first_user_message" not in js


def test__remember_no_duplicate_and_bounded_cache() -> None:
    # Prepare a known mapping
    ses._FINGERPRINT_TO_UUID.clear()
    ses._ORDER.clear()
    ses._remember("fp1", "sid1")
    assert ses._ORDER == ["fp1"]
    assert ses._FINGERPRINT_TO_UUID["fp1"] == "sid1"
    # Calling again should early-return and not append
    ses._remember("fp1", "sid-new")
    assert ses._ORDER == ["fp1"]
    assert ses._FINGERPRINT_TO_UUID["fp1"] == "sid1"
