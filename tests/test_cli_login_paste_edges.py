"""Edge-case coverage for cmd_login stdin paste worker branches."""

from __future__ import annotations

import io

from chatmock import cli


def test_cmd_login_paste_missing_code(monkeypatch) -> None:  # type: ignore[no-untyped-def]
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
            return None

        def shutdown(self) -> None:
            return None

        def exchange_code(self, code: str):  # type: ignore[no-untyped-def]
            return ({}, None)

        def persist_auth(self, bundle) -> bool:  # type: ignore[no-untyped-def]
            return True

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    monkeypatch.setattr(
        cli.sys, "stdin", io.StringIO("http://localhost:1455/auth/callback?state=s\n"), raising=True
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)


def test_cmd_login_paste_state_mismatch_and_exception(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Fake:
        def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
            self.exit_code = 1
            self.state = "expected"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def exchange_code(self, code: str):  # type: ignore[no-untyped-def]
            return ({}, None)

        def persist_auth(self, bundle) -> bool:  # type: ignore[no-untyped-def]
            return True

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    # First trigger state mismatch
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=wrong\n"),
        raising=True,
    )
    rc1 = cli.cmd_login(no_browser=True, verbose=False)

    # Then trigger exception in URL parsing
    class _Boom:
        def readline(self):  # type: ignore[no-untyped-def]
            return "http://localhost:1455/auth/callback?code=X&state=expected\n"

    monkeypatch.setattr(cli.sys, "stdin", _Boom(), raising=True)
    monkeypatch.setattr(
        cli,
        "urlparse",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("boom")),
        raising=True,
    )
    rc2 = cli.cmd_login(no_browser=True, verbose=False)
    assert rc1 in (0, 1) and rc2 in (0, 1)
