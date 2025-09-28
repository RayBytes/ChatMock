"""Cover signed-in info path when account_id is absent (no print)."""

from __future__ import annotations

import io
import sys

import pytest

from chatmock import cli


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_cli_info_signed_in_no_account_id(monkeypatch: pytest.MonkeyPatch) -> None:
    id_payload = {"email": "u@example.com"}
    access_payload = {"https://api.openai.com/auth": {"chatgpt_plan_type": "free"}}
    id_token = f"{_b64url(b'{}')}.{_b64url(__import__('json').dumps(id_payload).encode())}."
    access_token = f"{_b64url(b'{}')}.{_b64url(__import__('json').dumps(access_payload).encode())}."

    monkeypatch.setattr(cli, "read_auth_file", lambda: {"tokens": {}}, raising=True)
    # account_id is None here
    monkeypatch.setattr(
        cli, "load_chatgpt_tokens", lambda: (access_token, None, id_token), raising=True
    )

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        with pytest.raises(SystemExit):
            sys.argv = ["chatmock", "info"]
            cli.main()
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert "Signed in with ChatGPT" in out and "Account ID:" not in out
