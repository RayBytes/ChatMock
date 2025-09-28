"""Test early error_resp return in OpenAI chat route."""

from __future__ import annotations

import json

import pytest
from flask import jsonify, make_response

import chatmock.routes_openai as routes


def test_openai_chat_early_error_resp(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    with client.application.app_context():
        err = make_response(jsonify({"error": {"message": "nope"}}), 418)
    monkeypatch.setattr(routes, "start_upstream_request", lambda *a, **k: (None, err), raising=True)
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 418 and resp.get_json()["error"]["message"] == "nope"
