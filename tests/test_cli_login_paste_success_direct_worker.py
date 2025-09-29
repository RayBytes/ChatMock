"""Directly exercise cmd_login stdin paste success path to cover success lines."""

from __future__ import annotations

import types

from chatmock import cli


class _FakeHTTPD:
    def __init__(self, *_a: object, **_k: object) -> None:
        self.state = "s"
        self.exit_code = 1
        self._shutdown = False

    # context manager
    def __enter__(self) -> _FakeHTTPD:  # noqa: PYI034
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def auth_url(self) -> str:
        return "http://example/auth"

    def exchange_code(self, _code: object):
        return ({"ok": True}, None)

    def persist_auth(self, _bundle: object):
        return True

    def shutdown(self) -> None:
        self._shutdown = True

    def serve_forever(self) -> None:
        # Spin until shutdown is called by worker
        for _ in range(1000000):
            if self._shutdown or self.exit_code == 0:
                break


def test_cmd_login_paste_success(monkeypatch):
    """Direct worker paste path should set exit_code=0 and return 0."""
    monkeypatch.setattr(cli, "OAuthHTTPServer", _FakeHTTPD, raising=True)
    # Provide a valid redirect URL with matching state
    fake_stdin = types.SimpleNamespace(readline=lambda: "http://x/cb?code=abc&state=s\n")
    monkeypatch.setattr(cli, "sys", types.SimpleNamespace(stdin=fake_stdin))
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc == 0
