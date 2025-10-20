"""Cover get_effective_chatgpt_auth path when auth claims is non-dict."""

from __future__ import annotations

import base64
import json

from chatmock import utils


def _jwt_with_auth_claim(auth_claim):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"https://api.openai.com/auth": auth_claim}).encode()
    ).rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.sig"


def test_effective_auth_uses_none_when_claims_nondict(monkeypatch):
    token = _jwt_with_auth_claim("not-a-dict")
    monkeypatch.setattr(
        utils, "read_auth_file", lambda: {"tokens": {"id_token": token}}, raising=True
    )
    access, account = utils.get_effective_chatgpt_auth()
    assert access is None
    assert account is None
