"""Cover auth_url parameter composition in OAuth server."""

from __future__ import annotations

import urllib.parse

from chatmock import oauth


def test_auth_url_contains_expected_params() -> None:
    srv = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )
    url = srv.auth_url()
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert qs.get("client_id") == ["cid"] and qs.get("code_challenge_method") == ["S256"]
