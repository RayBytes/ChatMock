"""Invalid request format path in Ollama route."""

from __future__ import annotations

import json


def test_ollama_invalid_request_format(client: object) -> None:
    body = {"model": "gpt-5", "messages": "not-a-list"}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400
    assert "Invalid request format" in resp.get_json().get("error", "")
