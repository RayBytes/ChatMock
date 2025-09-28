"""Tests for JSON error responses and CORS headers."""

from __future__ import annotations

from chatmock.http import json_error


def test_json_error_builds_response(client: object) -> None:
    """json_error should set JSON body, status, and CORS headers."""
    with client.application.test_request_context("/", headers={}):
        resp = json_error("nope", status=418)
        assert resp.status_code == 418
        assert resp.mimetype == "application/json"
        body = resp.get_json()
        assert body == {"error": {"message": "nope"}}
        # CORS defaults
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert resp.headers.get("Access-Control-Allow-Methods") is not None
