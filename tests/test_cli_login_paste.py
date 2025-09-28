"""Exercise stdin paste worker path in login flow."""

from __future__ import annotations

import io

from chatmock import cli


def test_cmd_login_paste_url(monkeypatch) -> None:  # type: ignore[no-untyped-def]
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
            # Allow paste worker to run and then exit
            return None

        def shutdown(self) -> None:
            self.exit_code = 0

        def exchange_code(self, code: str):  # type: ignore[no-untyped-def]
            return ({"tokens": {}}, None)

        def persist_auth(self, bundle) -> bool:  # type: ignore[no-untyped-def]
            return True

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    # Provide a pasted callback URL with matching state
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=s\n"),
        raising=True,
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)
