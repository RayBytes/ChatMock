"""Cover OAuthHandler token exchange failure branch (500 error)."""

from __future__ import annotations

import threading

from chatmock import oauth


def test_oauth_handler_exchange_failure(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Exchange failure should produce HTTP 500 response."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    def _ex(_code: str):  # type: ignore[no-untyped-def]
        err = RuntimeError("boom")
        raise err

    httpd.exchange_code = _ex  # type: ignore[assignment]

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
    assert b"500 Token exchange failed" in data
