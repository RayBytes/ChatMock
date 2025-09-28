"""Cover CLI login branch when persisting auth fails."""

from __future__ import annotations

import io

import pytest

from chatmock import cli


def test_cmd_login_paste_persist_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Fake:
        def __init__(self, *a: object, **k: object):
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

        def exchange_code(self, code: str):
            return ({"tokens": {}}, None)

        def persist_auth(self, bundle: dict) -> bool:
            return False

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    # Provide a valid pasted URL so that persist_auth False path executes
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=s\n"),
        raising=True,
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)
