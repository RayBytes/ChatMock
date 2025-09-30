"""OpenAI chat route verbose logging on upstream error without extra tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _U:
    status_code = 400
    text = "bad"
    content = b'{"error": {"message": "bad"}}'


def test_openai_chat_verbose_error_no_tools(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.application.config["VERBOSE"] = True
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()
