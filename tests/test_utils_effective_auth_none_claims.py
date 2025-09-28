"""Test get_effective_chatgpt_auth when id_token has no account claim."""

from __future__ import annotations

import base64
import json

from chatmock import utils


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_get_effective_auth_no_account_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    id_claims = {"https://api.openai.com/auth": {}}  # no chatgpt_account_id
    id_token = f"{_b64url(b'{}')}.{_b64url(json.dumps(id_claims).encode())}."
    fake = {"tokens": {"access_token": "tok", "id_token": id_token}}
    monkeypatch.setattr(utils, "read_auth_file", lambda: fake, raising=True)
    access, account = utils.get_effective_chatgpt_auth()
    assert access == "tok" and account is None
