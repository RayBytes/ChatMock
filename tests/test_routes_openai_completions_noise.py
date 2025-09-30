"""Cover noise and empty data lines in non-stream Text Completions aggregator."""

from __future__ import annotations

from collections.abc import Iterator

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False) -> Iterator[bytes]:
        # Empty line, empty data, bad JSON, valid JSON, DONE (should break)
        yield b""
        yield b"data: "
        yield b"data: {not-json}"
        yield b'data: {"type": "response.output_text.delta", "delta": "X", "response": {"id": "r"}}'
        yield b"data: [DONE]"

    def close(self) -> None:
        return None


def test_openai_completions_nonstream_ignores_noise(client: object, monkeypatch: object) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    resp = client.post("/v1/completions", json={"model": "gpt-5", "prompt": "hi"})
    assert resp.status_code == 200
    assert resp.get_json().get("choices")
