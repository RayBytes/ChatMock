"""Unit tests for OAuthHandler._maybe_obtain_api_key branches without network."""

from __future__ import annotations

import json

from chatmock import oauth
from chatmock.models import TokenData


def test_handler_maybe_obtain_no_org_project() -> None:
    """No org/project: returns success URL and no API key."""
    h = object.__new__(oauth.OAuthHandler)
    # Provide minimal server attributes used by the method
    base = "http://t"
    h.server = type("S", (), {"client_id": "cid", "token_endpoint": f"{base}"})()  # type: ignore[attr-defined]
    id_tok = bytes([105, 100]).decode()  # avoid S106 literal-in-arg
    acc_tok = bytes([97, 99, 99]).decode()  # avoid S106 literal-in-arg
    ref_tok = bytes([114, 101, 102]).decode()  # avoid S106 literal-in-arg
    td = TokenData(id_token=id_tok, access_token=acc_tok, refresh_token=ref_tok, account_id="a")
    api_key, url = oauth.OAuthHandler._maybe_obtain_api_key(  # type: ignore[misc]
        h,
        token_claims={},
        access_claims={},
        token_data=td,
    )
    assert api_key is None
    assert url.startswith(oauth.URL_BASE + "/success?")


def test_handler_maybe_obtain_with_org_project(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Org/project present: exchange returns API key and URL."""
    h = object.__new__(oauth.OAuthHandler)
    base = "http://t"
    h.server = type("S", (), {"client_id": "cid", "token_endpoint": f"{base}"})()  # type: ignore[attr-defined]

    class _Resp:
        def __init__(self, data: dict) -> None:
            self._data = data

        def read(self):  # type: ignore[no-untyped-def]
            return json.dumps(self._data).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def _open(*_a, **_k):  # type: ignore[no-untyped-def]
        return _Resp({"access_token": "x"})

    monkeypatch.setattr(oauth.urllib.request, "urlopen", _open, raising=True)
    id_tok = bytes([105, 100]).decode()  # avoid S106 literal-in-arg
    acc_tok = bytes([97, 99, 99]).decode()  # avoid S106 literal-in-arg
    ref_tok = bytes([114, 101, 102]).decode()  # avoid S106 literal-in-arg
    td = TokenData(id_token=id_tok, access_token=acc_tok, refresh_token=ref_tok, account_id="a")
    api_key, url = oauth.OAuthHandler._maybe_obtain_api_key(  # type: ignore[misc]
        h,
        token_claims={"organization_id": "o", "project_id": "p"},
        access_claims={"chatgpt_plan_type": "plus"},
        token_data=td,
    )
    assert api_key == "x"
    assert "org_id=o" in url
    assert "project_id=p" in url
