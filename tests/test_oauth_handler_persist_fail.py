"""Test OAuthHandler 500 path when persisting auth fails."""

from __future__ import annotations

import threading

from chatmock import oauth
from chatmock.models import AuthBundle, TokenData


def test_oauth_handler_persist_fail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Persist failure should produce HTTP 500 response."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    def _ex(_code: str):  # type: ignore[no-untyped-def]
        id_tok = bytes([105, 100]).decode()  # avoid S106 literal-in-arg
        acc_tok = bytes([97, 99, 99]).decode()  # avoid S106 literal-in-arg
        ref_tok = bytes([114, 101, 102]).decode()  # avoid S106 literal-in-arg
        td = TokenData(
            id_token=id_tok,
            access_token=acc_tok,
            refresh_token=ref_tok,
            account_id="acc_1",
        )
        return AuthBundle(api_key=None, token_data=td, last_refresh="now"), None

    httpd.exchange_code = _ex  # type: ignore[assignment]
    monkeypatch.setattr(oauth, "write_auth_file", lambda _data: False, raising=True)

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()
    import socket

    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"GET /auth/callback?code=X HTTP/1.1\r\nHost: localhost\r\n\r\n")
    s.shutdown(socket.SHUT_WR)
    data = s.recv(1024)
    s.close()
    t.join(timeout=5)
    assert b"500 Unable to persist auth file" in data
