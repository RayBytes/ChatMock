"""Cover OpenAI chat non-stream path where no output_text is emitted."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        # No output_text deltas, just completed
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_openai_chat_nonstream_empty_content_message(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post(
        "/v1/chat/completions", data=json.dumps(body), content_type="application/json"
    )
    data = resp.get_json()
    assert resp.status_code == 200 and data["choices"][0]["message"]["content"] is None
