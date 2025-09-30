"""Tests for error paths in cmd_login paste worker."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from chatmock import cli


def test_cmd_login_paste_exchange_code_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test exchange_code raising OSError in paste worker (line 266-268)."""

    class _Fake:
        def __init__(self, *_a: object, **_k: object) -> None:  # type: ignore[no-untyped-def]
            self.exit_code = 1
            self.state = "s"

        def __enter__(self) -> _Fake:  # noqa: PYI034
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def exchange_code(self, _code: str):  # type: ignore[no-untyped-def]
            raise OSError("Exchange failed")

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=s\n"),
        raising=True,
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)


def test_cmd_login_paste_persist_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test persist_auth raising OSError in paste worker (line 275-276)."""

    class _Fake:
        def __init__(self, *_a: object, **_k: object) -> None:  # type: ignore[no-untyped-def]
            self.exit_code = 1
            self.state = "s"

        def __enter__(self) -> _Fake:  # noqa: PYI034
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            return None

        def shutdown(self) -> None:
            return None

        def exchange_code(self, _code: str):  # type: ignore[no-untyped-def]
            return ({"tokens": {}}, None)

        def persist_auth(self, _bundle: object) -> bool:  # type: ignore[no-untyped-def]
            raise OSError("Persist failed")

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=s\n"),
        raising=True,
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)
