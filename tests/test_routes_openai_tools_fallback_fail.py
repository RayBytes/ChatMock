"""Cover OpenAI chat tools fallback failure path returning RESPONSES_TOOLS_REJECTED."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


def test_chat_completions_tools_fallback_failure_returns_rejected(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _U1:
        status_code = 400
        text = "bad"
        content = b'{"error": {"message": "bad"}}'

    def fake_start(*a, **k):  # type: ignore[no-untyped-def]
        # First call returns an upstream error; second call returns (None, error_resp)
        if not getattr(fake_start, "called", False):
            fake_start.called = True  # type: ignore[attr-defined]
            return _U1(), None
        return None, (routes.jsonify({"error": {"message": "bad2"}}), 502)

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    data = resp.get_json()
    assert resp.status_code == 400
    assert data.get("error", {}).get("code") == "RESPONSES_TOOLS_REJECTED"
