"""Cover invalid JSON body error in OpenAI Chat Completions route."""

from __future__ import annotations


def test_chat_completions_invalid_json_returns_400(client: object) -> None:
    resp = client.post("/v1/chat/completions", data="{not-json}", content_type="application/json")
    data = resp.get_json()
    assert resp.status_code == 400
    assert data.get("error", {}).get("message") == "Invalid JSON body"
