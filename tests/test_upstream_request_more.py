"""More tests for upstream request payload handling."""

from __future__ import annotations

from typing import Any

import pytest

from chatmock import upstream


class _DummyResp:
    def __init__(self) -> None:
        self.status_code = 200


def test_start_upstream_request_includes_reasoning_and_tools(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_post(url: str, *, headers: dict, json: dict, stream: bool, timeout: int):  # type: ignore[override]
        captured.update(
            {"url": url, "headers": headers, "json": json, "stream": stream, "timeout": timeout}
        )
        return _DummyResp()

    monkeypatch.setattr(upstream.requests, "post", fake_post, raising=True)
    monkeypatch.setattr(
        upstream.utils_mod, "get_effective_chatgpt_auth", lambda: ("tok", "acc"), raising=True
    )

    with client.application.test_request_context("/v1/chat/completions", method="POST"):
        u, err = upstream.start_upstream_request(
            model="gpt-5-medium",
            input_items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
            tools=[{"type": "function", "function": {"name": "w"}}],
            tool_choice="auto",
            parallel_tool_calls=True,
            reasoning_param={"effort": "medium"},
        )
    assert err is None and u is not None
    # start_upstream_request forwards model verbatim; normalization occurs earlier in routing
    assert captured["json"]["model"] == "gpt-5-medium"
    assert captured["json"]["include"] == ["reasoning.encrypted_content"]
    assert (
        captured["json"]["tool_choice"] == "auto"
        and captured["json"]["parallel_tool_calls"] is True
    )
