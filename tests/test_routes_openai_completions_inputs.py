"""Completions prompt handling coverage."""

from __future__ import annotations

import json

import pytest

import chatmock.routes_openai as routes


class _Up:
    status_code = 200

    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_completions_prompt_list_and_suffix(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        routes, "start_upstream_request", lambda *a, **k: (_Up(), None), raising=True
    )
    # prompt as list concatenation
    body1 = {"model": "gpt-5", "prompt": ["a", "b"]}
    r1 = client.post("/v1/completions", data=json.dumps(body1), content_type="application/json")
    assert r1.status_code == 200
    # suffix fallback when prompt not string
    body2 = {"model": "gpt-5", "prompt": None, "suffix": "xyz"}
    r2 = client.post("/v1/completions", data=json.dumps(body2), content_type="application/json")
    assert r2.status_code == 200
