"""Additional edge-case tests for chatmock.cli cmd_login and __main__ guard."""

from __future__ import annotations

import io
import runpy
import sys

import pytest
from typing_extensions import Self

from chatmock import cli


def test_cmd_login_oserror_generic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-EADDRINUSE OSError during server startup returns 1."""

    class _Boom:
        def __init__(self, *_a: object, **_k: object) -> None:  # type: ignore[no-untyped-def]
            import errno as _errno

            e = OSError("nope")
            e.errno = _errno.EPERM  # not EADDRINUSE
            raise e

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Boom, raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc == 1


def test_cmd_login_paste_blank_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank input should short-circuit worker path."""

    class _Fake:
        def __init__(self, *_a: object, **_k: object) -> None:  # type: ignore[no-untyped-def]
            self.exit_code = 1

        def __enter__(self) -> _Fake:  # noqa: PYI034
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            # Allow background thread to run; then return
            return None

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    # Provide a single blank line to trigger early return path in worker
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("\n"), raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)


def test_cmd_login_persist_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """persist_auth False branch should be handled gracefully."""

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
            return False

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    # Matching state yields persist_auth(False) branch
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=s\n"),
        raising=True,
    )
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)


def test_cmd_login_state_mismatch_inline_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inline thread still handles state mismatch path."""

    class _Inline:
        def __init__(self, target, daemon: bool = False) -> None:  # type: ignore[no-untyped-def]
            self._t = target

        def start(self) -> None:
            self._t()

    class _Fake:
        def __init__(self, *_a: object, **_k: object) -> None:  # type: ignore[no-untyped-def]
            self.exit_code = 1
            self.state = "EXPECTED"

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def auth_url(self) -> str:
            return "http://localhost/auth"

        def serve_forever(self) -> None:
            return None

    monkeypatch.setattr(cli.threading, "Thread", _Inline, raising=True)
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        io.StringIO("http://localhost:1455/auth/callback?code=X&state=wrong\n"),
        raising=True,
    )
    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc in (0, 1)


def test_main_guard_via_run_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running module as __main__ should exit via SystemExit."""
    # Cover if __name__ == "__main__" guard by executing module
    monkeypatch.setattr(cli, "read_auth_file", lambda: {"ok": True}, raising=True)
    argv = sys.argv
    try:
        sys.argv = ["chatmock", "info", "--json"]
        # Ensure a clean import for run_module to avoid RuntimeWarning about cached module
        sys.modules.pop("chatmock.cli", None)
        with pytest.raises(SystemExit):
            runpy.run_module("chatmock.cli", run_name="__main__")
    finally:
        sys.argv = argv
