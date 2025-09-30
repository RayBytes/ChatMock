"""Extra coverage for OpenAI routes focusing on missed branches."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _UpOK:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_chat_empty_payload_defaults_messages_empty(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_UpOK(), None), raising=True
    )
    resp = client.post("/v1/chat/completions", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 200


def test_chat_responses_tools_non_dict_are_ignored(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_UpOK(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [], "responses_tools": [[], 1, {"type": "web_search"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200


def test_chat_upstream_error_invalid_json_decode_fallback(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U:
        status_code = 502
        content = b"not-json"
        text = "bad"

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_completions_upstream_error_invalid_json(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U:
        status_code = 500
        content = b"not-json"
        text = "bad"

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "prompt": "hi"}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 500
    assert "error" in resp.get_json()
