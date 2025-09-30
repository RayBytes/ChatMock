"""Basic models listing without exposing variants."""

from __future__ import annotations


def test_openai_models_basic(client: object) -> None:
    client.application.config["EXPOSE_REASONING_MODELS"] = False
    r = client.get("/v1/models")
    data = r.get_json()
    ids = [m["id"] for m in data["data"]]
    assert r.status_code == 200
    assert ids == ["gpt-5", "gpt-5-codex", "codex-mini"]
