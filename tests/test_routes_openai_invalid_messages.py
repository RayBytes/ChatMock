"""Cover invalid messages type path in OpenAI chat route."""

from __future__ import annotations

import json


def test_openai_chat_invalid_messages_type(client: object) -> None:
    body = {"model": "gpt-5", "messages": "not-a-list"}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 400
    assert "messages: []" in resp.get_json()["error"]["message"]
