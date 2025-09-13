from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Iterable, Tuple


def _sse_lines_tool_call() -> Iterable[bytes]:
    events = [
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "id": "item_1",
                "call_id": "call_123",
                "name": "mcp.call",
                "arguments": json.dumps({"server": "manuals", "tool": "search", "arguments": {"q": "brake"}}),
            },
            "response": {"id": "resp_1"},
        },
        {"type": "response.output_text.delta", "delta": "ok", "response": {"id": "resp_1"}},
        {"type": "response.completed", "response": {"id": "resp_1"}},
    ]
    for evt in events:
        yield ("data: " + json.dumps(evt) + "\n\n").encode("utf-8")
    yield b"data: [DONE]\n\n"


class _FakeUpstream:
    status_code = 200
    text = ""
    content = b""

    def iter_lines(self, decode_unicode: bool = False):  # noqa: ANN001
        return _sse_lines_tool_call()

    def close(self) -> None:  # noqa: D401
        return None


def _setup_app():
    # Mount local package path when running tests directly in repo clone
    here = os.path.abspath(os.path.dirname(__file__))
    root = os.path.dirname(here)
    if root not in sys.path:
        sys.path.insert(0, root)
    from chatmock.app import create_app  # type: ignore
    import chatmock.upstream as upstream  # type: ignore
    import chatmock.routes_openai as routes_openai  # type: ignore

    captured: Dict[str, Any] = {"tools": None, "tool_choice": None}

    def _stub_start_upstream_request(
        model: str,
        input_items: list[Dict[str, Any]],
        *,
        instructions: str | None = None,
        tools: list[Dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        parallel_tool_calls: bool = False,  # noqa: FBT001, FBT002
        reasoning_param: Dict[str, Any] | None = None,
    ) -> Tuple[_FakeUpstream | None, Any]:
        captured["tools"] = tools
        captured["tool_choice"] = tool_choice
        return _FakeUpstream(), None

    app = create_app(verbose=False)
    client = app.test_client()

    # Monkeypatch
    orig = upstream.start_upstream_request
    orig2 = routes_openai.start_upstream_request
    upstream.start_upstream_request = _stub_start_upstream_request  # type: ignore[assignment]
    routes_openai.start_upstream_request = _stub_start_upstream_request  # type: ignore[assignment]
    return client, captured, (upstream, routes_openai, orig, orig2)


def _teardown(patch_tuple) -> None:  # noqa: ANN001
    upstream, routes_openai, orig, orig2 = patch_tuple
    upstream.start_upstream_request = orig  # type: ignore[assignment]
    routes_openai.start_upstream_request = orig2  # type: ignore[assignment]


def test_no_responses_tools_keeps_default_behavior():
    client, captured, patch_tuple = _setup_app()
    try:
        payload = {
            "model": "gpt-5",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
        resp = client.post("/v1/chat/completions", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 200
        kinds = [t.get("type") for t in (captured.get("tools") or []) if isinstance(t, dict)]
        assert "web_search" not in kinds
    finally:
        _teardown(patch_tuple)


def test_responses_tools_forwarded_by_default():
    client, captured, patch_tuple = _setup_app()
    try:
        payload = {
            "model": "gpt-5",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "tools": [
                {"type": "function", "function": {"name": "ping", "parameters": {"type": "object"}}}
            ],
            "responses_tools": [
                {"type": "web_search"},
                {"type": "mcp", "server_label": "manuals", "server_url": "https://example"},
            ],
            "responses_tool_choice": "auto",
        }
        resp = client.post("/v1/chat/completions", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 200
        kinds = [t.get("type") for t in (captured.get("tools") or []) if isinstance(t, dict)]
        assert "function" in kinds
        assert "web_search" in kinds
        assert "mcp" in kinds
    finally:
        _teardown(patch_tuple)
