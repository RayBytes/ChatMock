"""Test HTTP error paths in OAuthHandler."""

from __future__ import annotations

import socket
import threading

from chatmock import oauth


def test_oauth_handler_non_callback_path() -> None:
    """Test non-callback path returns 404 (lines 230-232)."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()

    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"GET /some/other/path HTTP/1.1\r\nHost: localhost\r\n\r\n")
    s.shutdown(socket.SHUT_WR)
    data = s.recv(1024)
    s.close()
    t.join(timeout=5)

    assert b"404" in data
    assert b"Not Found" in data


def test_oauth_handler_missing_code() -> None:
    """Test callback without code returns 400 (lines 239-241)."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()

    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"GET /auth/callback HTTP/1.1\r\nHost: localhost\r\n\r\n")
    s.shutdown(socket.SHUT_WR)
    data = s.recv(1024)
    s.close()
    t.join(timeout=5)

    assert b"400" in data
    assert b"Missing auth code" in data


def test_oauth_handler_post_method() -> None:
    """Test POST method returns 404 (lines 269-270)."""
    httpd = oauth.OAuthHTTPServer(
        ("127.0.0.1", 0), oauth.OAuthHandler, home_dir=".", client_id="cid", verbose=False
    )

    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()

    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.sendall(b"POST /auth/callback HTTP/1.1\r\nHost: localhost\r\n\r\n")
    s.shutdown(socket.SHUT_WR)
    data = s.recv(1024)
    s.close()
    t.join(timeout=5)

    assert b"404" in data
    assert b"Not Found" in data
