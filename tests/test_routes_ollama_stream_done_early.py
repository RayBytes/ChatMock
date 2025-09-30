"""Cover Ollama streaming path when upstream sends [DONE] immediately."""

from __future__ import annotations

from typing import TYPE_CHECKING

import chatmock.routes_ollama as routes

if TYPE_CHECKING:
    import pytest


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b"data: [DONE]"

    def close(self) -> None:
        return None


def test_ollama_stream_done_early(client: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    body = {"model": "gpt-5", "messages": [{"role": "user", "content": "hi"}]}
    resp = client.post("/api/chat", json=body)
    assert resp.status_code == 200
    assert b'"done": true' in resp.data
