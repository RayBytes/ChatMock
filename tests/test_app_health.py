"""App-level health route and CORS behavior tests."""

from __future__ import annotations

from http import HTTPStatus


def test_health_has_cors_headers(client: object) -> None:
    """Health responds 200 and sets default CORS headers."""
    resp = client.get("/health")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json == {"status": "ok"}
    # After-request hook should set default CORS headers
    assert resp.headers.get("Access-Control-Allow-Origin") is not None
