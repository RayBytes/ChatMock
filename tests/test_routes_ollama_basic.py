"""Basic tests for Ollama-compatible routes."""

from __future__ import annotations

import json


def test_ollama_tags_variants_toggle(client: object) -> None:
    resp = client.get("/api/tags")
    assert resp.status_code == 200
    assert "models" in resp.get_json()
    client.application.config["EXPOSE_REASONING_MODELS"] = True
    resp2 = client.get("/api/tags")
    ids = [m["model"] for m in resp2.get_json()["models"]]
    assert any(mid.endswith("-high") for mid in ids)


def test_ollama_show_errors_and_success(client: object) -> None:
    # missing model
    resp = client.post("/api/show", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400
    # valid model
    resp2 = client.post(
        "/api/show", data=json.dumps({"model": "gpt-5"}), content_type="application/json"
    )
    assert resp2.status_code == 200
    assert "capabilities" in resp2.get_json()


def test_ollama_chat_invalid_json(client: object) -> None:
    resp = client.post("/api/chat", data="{not json}")
    assert resp.status_code == 400
