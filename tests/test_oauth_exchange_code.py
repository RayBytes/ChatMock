"""Tests for OAuthHTTPServer.exchange_code flow with patched network."""

from __future__ import annotations

import json

from chatmock import oauth


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_exchange_code_returns_bundle_and_success_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    srv = object.__new__(oauth.OAuthHTTPServer)
    srv.client_id = "cid"  # type: ignore[attr-defined]
    srv.redirect_uri = f"{oauth.URL_BASE}/auth/callback"  # type: ignore[attr-defined]
    srv.token_endpoint = "http://localhost/token"  # type: ignore[attr-defined]
    # Minimal PKCE object
    srv.pkce = type("_", (), {"code_verifier": "v"})()  # type: ignore[attr-defined]

    id_claims = {"https://api.openai.com/auth": {"chatgpt_account_id": "acc"}}
    id_token = f"{_b64url(b'{}')}.{_b64url(json.dumps(id_claims).encode())}."
    payload = {"id_token": id_token, "access_token": "at", "refresh_token": "rt"}

    class _Resp:
        def __init__(self, data: dict) -> None:
            self._data = data

        def read(self):  # type: ignore[no-untyped-def]
            return json.dumps(self._data).encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        oauth.urllib.request, "urlopen", lambda *a, **k: _Resp(payload), raising=True
    )
    bundle, success = oauth.OAuthHTTPServer.exchange_code(srv, "code")  # type: ignore[misc]
    assert bundle.token_data.id_token and success.startswith(oauth.URL_BASE + "/success")
