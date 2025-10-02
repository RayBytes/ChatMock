"""Tests for upstream error handling branch and CORS headers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests

from chatmock import upstream

if TYPE_CHECKING:
    import pytest


def test_start_upstream_request_network_error(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        msg = "boom"
        raise requests.RequestException(msg)

    monkeypatch.setattr(upstream.requests, "post", boom, raising=True)
    monkeypatch.setattr(
        upstream.utils_mod, "get_effective_chatgpt_auth", lambda: ("tok", "acc"), raising=True
    )

    with client.application.test_request_context("/v1/chat/completions", method="POST"):
        u, err = upstream.start_upstream_request(
            model="gpt-5",
            input_items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
        )
    assert u is None
    assert err is not None
    assert err.status_code == 502
    assert err.headers.get("Access-Control-Allow-Origin") is not None
