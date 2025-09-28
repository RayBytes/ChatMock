"""Unit tests for OAuthHandler._maybe_obtain_api_key branches without network."""

from __future__ import annotations

import json

from chatmock import oauth
from chatmock.models import TokenData


def test_handler_maybe_obtain_no_org_project() -> None:
    h = object.__new__(oauth.OAuthHandler)
    # Provide minimal server attributes used by the method
    h.server = type("S", (), {"client_id": "cid", "token_endpoint": "http://t"})()  # type: ignore[attr-defined]
    td = TokenData(id_token="id", access_token="acc", refresh_token="ref", account_id="a")
    api_key, url = oauth.OAuthHandler._maybe_obtain_api_key(  # type: ignore[misc]
        h,
        token_claims={},
        access_claims={},
        token_data=td,
    )
    assert api_key is None and url.startswith(oauth.URL_BASE + "/success?")


def test_handler_maybe_obtain_with_org_project(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    h = object.__new__(oauth.OAuthHandler)
    h.server = type("S", (), {"client_id": "cid", "token_endpoint": "http://t"})()  # type: ignore[attr-defined]

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
        oauth.urllib.request, "urlopen", lambda *a, **k: _Resp({"access_token": "x"}), raising=True
    )
    td = TokenData(id_token="id", access_token="acc", refresh_token="ref", account_id="a")
    api_key, url = oauth.OAuthHandler._maybe_obtain_api_key(  # type: ignore[misc]
        h,
        token_claims={"organization_id": "o", "project_id": "p"},
        access_claims={"chatgpt_plan_type": "plus"},
        token_data=td,
    )
    assert api_key == "x" and "org_id=o" in url and "project_id=p" in url
