"""Error path for text completions route."""

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


def test_completions_upstream_error(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_U(), None), raising=True
    )
    body = {"model": "gpt-5", "prompt": "hi"}
    resp = client.post("/v1/completions", data=json.dumps(body), content_type="application/json")
    assert resp.status_code == 400
    assert "error" in resp.get_json()
