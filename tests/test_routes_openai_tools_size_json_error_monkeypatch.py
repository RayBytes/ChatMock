"""Force TypeError in json.dumps(extra_tools) to hit size-except path in OpenAI route."""

from __future__ import annotations

import json as _json

import pytest

import chatmock.routes_openai as routes


def test_openai_responses_tools_size_json_error_monkeypatch(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange a json.dumps that raises TypeError for our extra_tools argument
    orig_dumps = routes.json.dumps

    def fake_dumps(obj, *a, **k):  # type: ignore[no-untyped-def]
        if (
            isinstance(obj, list)
            and obj
            and isinstance(obj[0], dict)
            and obj[0].get("type") in {"web_search", "web_search_preview"}
        ):
            raise TypeError("boom")
        return orig_dumps(obj, *a, **k)

    class _U:
        status_code = 200

        def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
            yield b'data: {"type": "response.completed", "response": {}}'

        def close(self):
            return None

    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_U(), None), raising=True
    )
    monkeypatch.setattr(
        routes, "json", type("J", (), {"dumps": fake_dumps, "loads": routes.json.loads})
    )

    body = {
        "model": "gpt-5",
        "messages": [],
        "responses_tools": [{"type": "web_search"}],
        "stream": True,
    }
    resp = client.post(
        "/v1/chat/completions", data=_json.dumps(body), content_type="application/json"
    )
    assert resp.status_code == 200
