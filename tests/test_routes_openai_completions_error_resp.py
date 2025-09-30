"""Cover early error_resp return in Text Completions route."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from flask import jsonify, make_response

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_completions_early_error_resp(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    with client.application.app_context():
        err = make_response(jsonify({"error": {"message": "nope"}}), 418)
    monkeypatch.setattr(routes, "start_upstream_request", lambda *a, **k: (None, err), raising=True)
    body = {"model": "gpt-5", "prompt": "hi"}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 418
    assert resp.get_json()["error"]["message"] == "nope"
