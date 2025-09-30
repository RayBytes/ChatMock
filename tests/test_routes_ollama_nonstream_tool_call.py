"""Cover Ollama non-stream tool_call aggregation branch."""

from __future__ import annotations

import json

import chatmock.routes_ollama as routes


class _U:
    status_code = 200
    content = b""
    text = ""

    def __init__(self, events) -> None:
        self._lines = [f"data: {json.dumps(e)}".encode() for e in events]

    def iter_lines(self, decode_unicode: bool = False):
        yield from self._lines

    def close(self):
        return None


def test_ollama_nonstream_records_function_call_tool(client):
    def fake_start(model, input_items, **kw):
        ev = [
            {
                "type": "response.output_item.done",
                "item": {"type": "function_call", "id": "c1", "name": "f", "arguments": "{}"},
            },
            {"type": "response.completed"},
        ]
        return _U(ev), None

    routes.start_upstream_request, orig = fake_start, routes.start_upstream_request
    try:
        body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}], "stream": False}
        resp = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["message"].get("tool_calls")
        assert data["message"]["tool_calls"][0]["function"]["name"] == "f"
    finally:
        routes.start_upstream_request = orig
