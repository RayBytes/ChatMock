"""Tests for OAuth server token exchange helper branches."""

from __future__ import annotations

import json

from chatmock import oauth
from chatmock.models import TokenData


def test_maybe_obtain_api_key_no_org_project() -> None:
    srv = object.__new__(oauth.OAuthHTTPServer)
    srv.client_id = "cid"  # type: ignore[attr-defined]
    srv.token_endpoint = "http://localhost/token"  # type: ignore[attr-defined]
    td = TokenData(id_token="id", access_token="acc", refresh_token="ref", account_id="a")
    api_key, success = oauth.OAuthHTTPServer.maybe_obtain_api_key(  # type: ignore[misc]
        srv,
        token_claims={},
        access_claims={},
        token_data=td,
    )
    assert api_key is None and isinstance(success, str) and success.startswith(oauth.URL_BASE)


def test_maybe_obtain_api_key_with_org_project(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    srv = object.__new__(oauth.OAuthHTTPServer)
    srv.client_id = "cid"  # type: ignore[attr-defined]
    srv.token_endpoint = "http://localhost/token"  # type: ignore[attr-defined]

    class _Resp:
        def __init__(self, data: dict) -> None:
            self._data = data

        def read(self):  # type: ignore[no-untyped-def]
            return json.dumps(self._data).encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(req, context=None):  # type: ignore[no-untyped-def]
        return _Resp({"access_token": "exchanged"})

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen, raising=True)
    td = TokenData(id_token="id", access_token="acc", refresh_token="ref", account_id="a")
    api_key, success = oauth.OAuthHTTPServer.maybe_obtain_api_key(  # type: ignore[misc]
        srv,
        token_claims={"organization_id": "org", "project_id": "proj"},
        access_claims={"chatgpt_plan_type": "plus"},
        token_data=td,
    )
    assert api_key == "exchanged" and "org_id=org" in success and "project_id=proj" in success
