"""Cover invalid JSON body error in Text Completions route."""

from __future__ import annotations


def test_completions_invalid_json_returns_400(client: object) -> None:
    resp = client.post("/v1/completions", data="{not-json}", content_type="application/json")
    assert resp.status_code == 400
    assert "Invalid JSON body" in resp.get_json()["error"]["message"]
