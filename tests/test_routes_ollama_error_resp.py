"""Cover early error_resp return path in Ollama chat route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from flask import jsonify, make_response

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


def test_ollama_chat_early_error_resp(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    with client.application.app_context():
        err = make_response(jsonify({"error": {"message": "boom"}}), 418)
    monkeypatch.setattr(routes, "start_upstream_request", lambda *_a, **_k: (None, err), raising=True)
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    r = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 418
    assert r.get_json()["error"]["message"] == "boom"
