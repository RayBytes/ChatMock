"""Tests for upstream request helper behavior."""

from __future__ import annotations

from chatmock.upstream import start_upstream_request


def test_start_upstream_request_missing_creds(client: object, monkeypatch) -> None:
    """When creds are missing, returns a 401 error response and no upstream."""
    # Force missing credentials
    from chatmock import utils as utils_mod  # lazy import via package

    monkeypatch.setattr(utils_mod, "get_effective_chatgpt_auth", lambda: (None, None), raising=True)

    with client.application.test_request_context("/v1/chat/completions", method="POST"):
        upstream, error_resp = start_upstream_request(
            model="gpt-5",
            input_items=[
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
        )

    assert upstream is None
    assert error_resp is not None
    assert error_resp.status_code == 401
