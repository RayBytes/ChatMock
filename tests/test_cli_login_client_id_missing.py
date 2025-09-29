"""Cover early error path when CLIENT_ID_DEFAULT is missing."""

from __future__ import annotations

from chatmock import cli


def test_cmd_login_missing_client_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Return exit code 1 when default client ID is missing."""
    monkeypatch.setattr(cli, "CLIENT_ID_DEFAULT", "", raising=True)
    rc = cli.cmd_login(no_browser=True, verbose=False)
    assert rc == 1
