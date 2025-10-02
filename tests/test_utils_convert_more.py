"""More tests for chatmock.utils conversions to raise coverage."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_convert_chat_messages_image_data_url_normalization() -> None:
    # base64 without padding should be normalized (length multiple of 4)
    raw = "data:image/png;base64,YWJj"  # "abc" no padding
    msgs = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": raw}}],
        }
    ]
    out = convert_chat_messages_to_responses_input(msgs)
    url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    assert isinstance(url, str)
    assert len(url.split(",", 1)[1]) % 4 == 0
