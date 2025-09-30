"""Tests for OAuth server token exchange helper branches."""

from __future__ import annotations

import json

from typing_extensions import Self

from chatmock import oauth
from chatmock.models import TokenData


def test_maybe_obtain_api_key_no_org_project() -> None:
    """When org/project missing, returns success URL and no key."""
    srv = object.__new__(oauth.OAuthHTTPServer)
    srv.client_id = "cid"  # type: ignore[attr-defined]
    base = "http://localhost"  # avoid S105 hardcoded password false positive
    srv.token_endpoint = f"{base}/token"  # type: ignore[attr-defined]
    id_tok = "id"  # avoid S106 literal-in-arg
    acc_tok = "acc"  # avoid S106 literal-in-arg
    ref_tok = "ref"  # avoid S106 literal-in-arg
    td = TokenData(id_token=id_tok, access_token=acc_tok, refresh_token=ref_tok, account_id="a")
    api_key, success = oauth.OAuthHTTPServer.maybe_obtain_api_key(  # type: ignore[misc]
        srv,
        token_claims={},
        access_claims={},
        token_data=td,
    )
    assert api_key is None
    assert isinstance(success, str)
    assert success.startswith(oauth.URL_BASE)


def test_maybe_obtain_api_key_with_org_project(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """When org/project present, exchanges and returns key + URL."""
    srv = object.__new__(oauth.OAuthHTTPServer)
    srv.client_id = "cid"  # type: ignore[attr-defined]
    base = "http://localhost"
    srv.token_endpoint = f"{base}/token"  # type: ignore[attr-defined]

    class _Resp:
        def __init__(self, data: dict) -> None:
            self._data = data

        def read(self):  # type: ignore[no-untyped-def]
            return json.dumps(self._data).encode()

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_urlopen(req, context=None):  # type: ignore[no-untyped-def]
        return _Resp({"access_token": "exchanged"})

    monkeypatch.setattr(oauth.urllib.request, "urlopen", fake_urlopen, raising=True)
    id_tok = "id"  # avoid S106 literal-in-arg
    acc_tok = "acc"  # avoid S106 literal-in-arg
    ref_tok = "ref"  # avoid S106 literal-in-arg
    td = TokenData(id_token=id_tok, access_token=acc_tok, refresh_token=ref_tok, account_id="a")
    api_key, success = oauth.OAuthHTTPServer.maybe_obtain_api_key(  # type: ignore[misc]
        srv,
        token_claims={"organization_id": "org", "project_id": "proj"},
        access_claims={"chatgpt_plan_type": "plus"},
        token_data=td,
    )
    assert api_key == "exchanged"
    assert "org_id=org" in success
    assert "project_id=proj" in success
