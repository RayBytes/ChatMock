"""Enable VERBOSE to exercise logging branches in routes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_ollama as r_ollama
import chatmock.routes_openai as r_openai

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 400
    text = "bad"
    content = b'{"error": {"message": "bad"}}'


def test_verbose_logs_openai_error_and_fallback(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["VERBOSE"] = True
    calls = {"n": 0}

    class _U2:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    def fake_start(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return (_Up(), None) if calls["n"] == 1 else (_U2(), None)

    monkeypatch.setattr(r_openai, "start_upstream_request", fake_start, raising=True)
    monkeypatch.setattr(
        r_openai, "sse_translate_chat", lambda *_a, **_k: [b"data: [DONE]\n\n"], raising=True
    )
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
    assert calls["n"] == 2


def test_verbose_logs_ollama_error_path(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    client.application.config["VERBOSE"] = True
    monkeypatch.setattr(
        r_ollama, "start_upstream_request", lambda *_a, **_k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400
