"""Misc coverage for oauth helpers: persist_auth, log_message, redirects, delayed shutdown."""

from __future__ import annotations

import pytest

from chatmock import oauth
from chatmock.models import AuthBundle, TokenData


def test_persist_auth_invokes_write(monkeypatch: pytest.MonkeyPatch) -> None:
    srv = object.__new__(oauth.OAuthHTTPServer)
    bundle = AuthBundle(
        api_key="k", token_data=TokenData("id", "acc", "ref", "acc_1"), last_refresh="now"
    )
    called = {"ok": False}

    def _write(data: dict) -> bool:  # type: ignore[no-untyped-def]
        called["ok"] = True
        # basic shape check
        return data.get("tokens", {}).get("id_token") == "id"

    monkeypatch.setattr(oauth, "write_auth_file", _write, raising=True)
    assert oauth.OAuthHTTPServer.persist_auth(srv, bundle) is True and called["ok"]  # type: S101


def test_handler_log_message_delegates_on_verbose() -> None:  # type: ignore[no-untyped-def]
    class _Fake(oauth.OAuthHandler):  # type: ignore[misc]
        def __init__(self):
            # Avoid BaseHTTPRequestHandler initialization
            pass

        # Avoid BaseHTTPRequestHandler initialization; only provide what's needed
        server = type("S", (), {"verbose": True})()
        requestline = "GET / HTTP/1.1"

        def address_string(self):
            return "127.0.0.1"

        def log_date_time_string(self):
            return "now"

    # Should not raise
    oauth.OAuthHandler.log_message(_Fake(), "%s", "ok")


def test_send_redirect_calls_headers() -> None:  # type: ignore[no-untyped-def]
    called = {"status": None, "loc": None, "ended": False}

    class _H:
        def send_response(self, code: int) -> None:
            called["status"] = code

        def send_header(self, k: str, v: str) -> None:
            if k.lower() == "location":
                called["loc"] = v

        def end_headers(self) -> None:
            called["ended"] = True

    oauth.OAuthHandler._send_redirect(_H(), "http://x/y")
    assert called["status"] == 302 and called["loc"] == "http://x/y" and called["ended"]


def test_shutdown_after_delay_executes_target(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replace Thread to execute inline without real threads or sleeps
    class _Inline:
        def __init__(self, target, daemon=False):  # type: ignore[no-untyped-def]
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(oauth.threading, "Thread", _Inline, raising=True)
    called = {"n": 0}

    class _H:
        def _shutdown(self) -> None:
            called["n"] += 1

    oauth.OAuthHandler._shutdown_after_delay(_H(), 0.0)
    assert called["n"] == 1


def test_success_page_flush_error_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drive the "/success" branch with a fake handler where flush raises
    class _H:
        path = "/success"

        def _send_html(self, body: str) -> None:  # type: ignore[no-untyped-def]
            return None

        class _W:
            def flush(self):  # type: ignore[no-untyped-def]
                raise RuntimeError("boom")

        wfile = _W()

        def _shutdown_after_delay(self, seconds: float = 2.0) -> None:  # type: ignore[no-untyped-def]
            return None

    # Should not raise even if flushing fails
    oauth.OAuthHandler.do_GET(_H())
