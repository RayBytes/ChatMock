"""Basic tests hitting OpenAI-compatible routes for error and simple paths."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


def test_chat_completions_invalid_json(client: object) -> None:
    resp = client.post("/v1/chat/completions", data="{not json}")
    assert resp.status_code == 400
    assert resp.get_json()["error"]["message"] == "Invalid JSON body"


def test_chat_completions_messages_not_list(client: object) -> None:
    resp = client.post(
        "/v1/chat/completions",
        data=json.dumps({"messages": "oops"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "messages: []" in resp.get_json()["error"]["message"]


def test_models_list_default_and_variants(client: object) -> None:
    # default: only base ids
    resp = client.get("/v1/models")
    ids = [m["id"] for m in resp.get_json()["data"]]
    assert "gpt-5" in ids and "gpt-5-codex" in ids
    # enable variants
    client.application.config["EXPOSE_REASONING_MODELS"] = True
    resp2 = client.get("/v1/models")
    ids2 = [m["id"] for m in resp2.get_json()["data"]]
    assert any(mid.endswith("-high") for mid in ids2)


class _FakeUpstream:
    status_code = 200
    text = ""

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {\n\t"type": "response.output_text.delta", "delta": "Hello"}'
        yield b'data: {"type": "response.completed"}'

    def close(self) -> None:
        return None


def test_text_completions_nonstream_happy_path(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_FakeUpstream(), None), raising=True
    )
    resp = client.post(
        "/v1/completions",
        data=json.dumps({"model": "gpt-5", "prompt": "hi"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["choices"][0]["text"] == "Hello"
