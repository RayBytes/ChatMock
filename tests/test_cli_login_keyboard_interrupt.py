"""Cover KeyboardInterrupt path in cmd_login."""

from __future__ import annotations

from chatmock import cli


def test_cmd_login_keyboard_interrupt(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Handle KeyboardInterrupt during serve_forever and return 1."""

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
            raise KeyboardInterrupt

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Fake, raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc == 1
