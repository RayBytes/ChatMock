"""Coverage for parse_jwt_claims and generate_pkce."""

from __future__ import annotations

import base64
import json
import re

from chatmock import utils


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_parse_jwt_claims_valid_and_invalid() -> None:
    claims = {"k": 1}
    tok = f"{_b64url(b'{}')}.{_b64url(json.dumps(claims).encode())}.sig"
    assert utils.parse_jwt_claims(tok) == claims
    # invalid formats/decodes
    assert utils.parse_jwt_claims("") is None
    assert utils.parse_jwt_claims("a.b") is None
    bad = f"a.{_b64url(b'not-json')}.b"
    assert utils.parse_jwt_claims(bad) is None


def test_generate_pkce_shapes() -> None:
    pk = utils.generate_pkce()
    assert isinstance(pk.code_verifier, str) and len(pk.code_verifier) == 128
    assert isinstance(pk.code_challenge, str) and re.fullmatch(r"[A-Za-z0-9_-]+", pk.code_challenge)
