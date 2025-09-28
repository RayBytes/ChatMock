"""Exercise image data URL normalization path in convert_chat_messages_to_responses_input."""

from __future__ import annotations

from chatmock.utils import convert_chat_messages_to_responses_input


def test_image_data_url_normalization_with_dash_underscore_and_padding() -> None:
    # Construct a data URL where payload has '-' and '_' and missing padding
    payload = "YWJj-_-"  # 'abc' with characters to normalize; padding will be added
    raw = f"data:image/png;base64,{payload}"
    msgs = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": raw}}]}]
    out = convert_chat_messages_to_responses_input(msgs)
    url = out[0]["content"][0]["image_url"]  # type: ignore[index]
    assert (
        isinstance(url, str)
        and url.startswith("data:image/png;base64,")
        and len(url.split(",", 1)[1]) % 4 == 0
    )
