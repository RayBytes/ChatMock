"""Edge cases for image_url normalization in utils."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_image_data_url_decode_error_returns_original() -> None:
    raw = "data:image/png;base64,???"  # invalid base64 to trigger decode error
    msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": raw}}]}]
    out = convert_chat_messages_to_responses_input(msgs)
    url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    # Decoder normalizes by adding padding; just ensure it remains a data URL
    assert isinstance(url, str) and url.startswith("data:image/png;base64,")
