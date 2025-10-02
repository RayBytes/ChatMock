"""Test OAuth handler success path including HTML response."""

from __future__ import annotations

import socket
import threading

from chatmock import oauth
from chatmock.models import AuthBundle, TokenData


def test_oauth_handler_success_with_html(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Test successful OAuth flow with HTML response (lines 261-262, 283-288)."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    def _ex(_code: str):  # type: ignore[no-untyped-def]
        id_tok = bytes([105, 100]).decode()
        acc_tok = bytes([97, 99, 99]).decode()
        ref_tok = bytes([114, 101, 102]).decode()
        td = TokenData(
            id_token=id_tok,
            access_token=acc_tok,
            refresh_token=ref_tok,
            account_id="acc_1",
        )
        return AuthBundle(api_key=None, token_data=td, last_refresh="now"), None

    httpd.exchange_code = _ex  # type: ignore[assignment]

    # Mock write_auth_file to return True (success)
    monkeypatch.setattr(oauth, "write_auth_file", lambda _data: True, raising=True)

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()

    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"GET /auth/callback?code=X HTTP/1.1\r\nHost: localhost\r\n\r\n")
    s.shutdown(socket.SHUT_WR)
    data = s.recv(4096)
    s.close()
    t.join(timeout=5)

    # Verify success response with HTML
    assert b"200" in data or b"HTTP/1.0 200" in data or b"HTTP/1.1 200" in data
    assert b"Content-Type: text/html" in data
    assert b"Content-Length:" in data

    # Verify exit code was set to 0
    assert httpd.exit_code == 0
