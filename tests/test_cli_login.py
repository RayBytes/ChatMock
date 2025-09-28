"""CLI login path test with a fake OAuth server."""

from __future__ import annotations

from chatmock import cli


def test_cmd_login_uses_fake_server_and_browser_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Fake:
        def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
            self.exit_code = 1
            self.state = "s"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            # Simulate graceful exit
            self.exit_code = 0

        def shutdown(self) -> None:
            return None

        def exchange_code(self, code: str):  # type: ignore[no-untyped-def]
            return ({}, None)

        def persist_auth(self, bundle) -> bool:  # type: ignore[no-untyped-def]
            return True

    class _WB:
        class Error(Exception):
            pass

        @staticmethod
        def open(*a, **k):  # type: ignore[no-untyped-def]
            raise _WB.Error("boom")

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    monkeypatch.setattr(cli, "webbrowser", _WB, raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc == 0

    # Exercise browser error branch
    rc2 = cli.cmd_login(no_browser=False, verbose=False)
    assert rc2 == 0
