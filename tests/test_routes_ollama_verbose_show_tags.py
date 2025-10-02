"""Enable VERBOSE for tags and show to exercise logging branches."""

from __future__ import annotations


def test_verbose_ollama_tags_and_show(client: object) -> None:
    client.application.config["VERBOSE"] = True
    r1 = client.get("/api/tags")
    assert r1.status_code == 200
    r2 = client.post("/api/show", json={"model": "gpt-5"})
    assert r2.status_code == 200
