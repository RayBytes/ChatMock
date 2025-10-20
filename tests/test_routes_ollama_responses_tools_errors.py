"""Cover error branches in Ollama responses_tools handling."""

from __future__ import annotations

import json


def test_responses_tools_unsupported_type(client):
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "responses_tools": [{"type": "not_supported"}],
    }
    resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400


def test_responses_tools_default_disabled_by_choice_none(client):
    client.application.config["DEFAULT_WEB_SEARCH"] = True
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "responses_tool_choice": "none",
    }

    # Minimal upstream that immediately completes
    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):
            yield b'data: {"type": "response.completed"}'

        def close(self):
            return None

    import chatmock.routes_ollama as routes

    def fake_start(model, input_items, **kw):
        return _U(), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig
