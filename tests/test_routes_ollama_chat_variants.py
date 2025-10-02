"""Additional coverage for /api/chat variants (verbose, invalid, system reordering)."""

from __future__ import annotations

import json


def test_ollama_chat_invalid_request_format(client):
    resp = client.post("/api/chat", data=json.dumps({"model": 5}), content_type="application/json")
    assert resp.status_code == 400


def test_ollama_chat_verbose_logs_and_system_move(client):
    client.application.config["VERBOSE"] = True

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):
            yield b'data: {"type": "response.completed"}'

        def close(self):
            return None

    import chatmock.routes_ollama as routes

    def fake_start(model, input_items, **kw):
        # Ensure system message was moved to front as user
        assert input_items[0]["role"] == "user"
        return _U(), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        body = {
            "model": "gpt-5",
            "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            "stream": False,
        }
        resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
        assert resp.status_code == 200
    finally:
        routes.start_upstream_request = orig
