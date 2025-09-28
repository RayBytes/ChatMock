"""Cover noise/empty/invalid branches in _ollama_stream_gen."""

from __future__ import annotations

import chatmock.routes_ollama as routes


class _Up:
    def __init__(self) -> None:
        self._lines = [
            b"",  # empty -> continue
            b"no-prefix",  # not starting with data: -> continue
            b"data: ",  # empty data -> continue
            b"data: {not-json}",  # json error -> continue
            b'data: {"type": "response.completed", "response": {}}',
        ]

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        for l in self._lines:
            yield l

    def close(self) -> None:
        return None


def test_stream_generator_ignores_noise_lines() -> None:
    out = b"".join(
        s.encode() if isinstance(s, str) else s
        for s in routes._ollama_stream_gen(_Up(), "gpt-5", "2023-01-01T00:00:00Z", "think-tags")
    )
    # Should at least produce the final done object
    assert b'"done": true' in out.lower()
