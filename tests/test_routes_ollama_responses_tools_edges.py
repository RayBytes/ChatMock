"""Edge cases for responses_tools handling in Ollama route."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_ollama_responses_tools_ignores_non_dict_entries(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
        "responses_tools": [123, {"type": "web_search"}],
        "stream": True,
    }
    r = client.post("/api/chat", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 200
