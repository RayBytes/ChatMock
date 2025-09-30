"""Basic unit tests for lightweight utilities in chatmock.utils."""

from __future__ import annotations

import base64
import json

from chatmock.utils import (
    eprint,
    generate_pkce,
    get_home_dir,
    parse_jwt_claims,
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_eprint_writes_stderr(capsys: object) -> None:
    """Eprint writes to stderr and not stdout."""
    eprint("hello", "world")
    out = capsys.readouterr()
    assert "hello world" in out.err


def test_get_home_dir_env_overrides(temp_home_env: object) -> None:
    """get_home_dir prefers env vars over default path."""
    assert get_home_dir() == str(temp_home_env)


def test_parse_jwt_claims_valid() -> None:
    """Valid JWT payloads are decoded."""
    header = _b64url(json.dumps({"alg": "none"}).encode())
    payload = {"sub": "abc", "n": 1}
    token = f"{header}.{_b64url(json.dumps(payload).encode())}."
    claims = parse_jwt_claims(token)
    assert claims == payload


def test_parse_jwt_claims_invalid() -> None:
    """Invalid JWTs return None (no crash)."""
    assert parse_jwt_claims("not.a.jwt") is None


def test_generate_pkce_shapes() -> None:
    """PKCE fields exist and have reasonable shapes."""
    pkce = generate_pkce()
    assert isinstance(pkce.code_verifier, str)
    assert len(pkce.code_verifier) >= 64
    assert isinstance(pkce.code_challenge, str)
    assert pkce.code_challenge
