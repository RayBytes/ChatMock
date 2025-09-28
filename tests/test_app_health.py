"""App-level health route and CORS behavior tests."""

from __future__ import annotations


def test_health_has_cors_headers(client: object) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json == {"status": "ok"}
    # After-request hook should set default CORS headers
    assert resp.headers.get("Access-Control-Allow-Origin") is not None
