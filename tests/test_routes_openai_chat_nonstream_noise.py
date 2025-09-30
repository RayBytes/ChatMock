"""Cover noise, empty, and bad-JSON branches in OpenAI chat non-stream aggregator; include usage."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        yield from self._lines

    def close(self) -> None:
        return None


def test_chat_nonstream_ignores_noise_and_includes_usage(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = [
        b"",  # empty raw
        b"noise",  # no data: prefix
        b"data: ",  # empty data
        b"data: {not-json}",  # bad json
        b'data: {"type": "response.output_text.delta", "delta": "Hello", "response": {"id": "r"}}',
        b'data: {"type": "response.completed", "response": {"usage": '
        b'{"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}}}',
    ]
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *_a, **_k: (_Up(lines), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    r = client.post("/v1/chat/completions", data=json.dumps(body), content_type="application/json")
    data = r.get_json()
    assert r.status_code == 200
    assert data["choices"][0]["message"]["content"] == "Hello"
    assert data.get("usage", {}).get("total_tokens") == 3
