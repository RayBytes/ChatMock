"""Tests for effective auth derivation from stored tokens."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any

from chatmock import utils

if TYPE_CHECKING:
    import pytest


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_get_effective_chatgpt_auth_uses_id_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """When account_id is missing, derive it from id_token claims."""
    claims: dict[str, Any] = {"https://api.openai.com/auth": {"chatgpt_account_id": "acc_123"}}
    id_token = f"{_b64url(b'{}')}.{_b64url(json.dumps(claims).encode())}."
    fake_auth = {"tokens": {"access_token": "tok", "id_token": id_token}}

    monkeypatch.setattr(utils, "read_auth_file", lambda: fake_auth)
    access, account = utils.get_effective_chatgpt_auth()
    assert access == "tok"
    assert account == "acc_123"
