"""Cover additional CLI main branches and errors."""

from __future__ import annotations

import io
import sys

import pytest

from chatmock import cli


def _run(argv: list[str]) -> tuple[str, int]:
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        with pytest.raises(SystemExit) as ex:
            sys.argv = ["chatmock"] + argv
            cli.main()
    finally:
        sys.stdout = old
    return buf.getvalue(), int(getattr(ex.value, "code", 0))


def test_main_info_various_plans(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_parse(token):  # type: ignore[no-untyped-def]
        if token == "id":
            return {"email": "u@example.com"}
        return {"https://api.openai.com/auth": {"chatgpt_plan_type": "team"}}

    monkeypatch.setattr(cli, "read_auth_file", lambda: {"tokens": {}}, raising=True)
    monkeypatch.setattr(cli, "load_chatgpt_tokens", lambda: ("access", "acc_1", "id"), raising=True)
    monkeypatch.setattr(cli, "parse_jwt_claims", fake_parse, raising=True)
    out, code = _run(["info"])
    assert "Plan: Team" in out and code == 0


def test_main_login_bind_in_use(monkeypatch: pytest.MonkeyPatch) -> None:
    import errno as _errno

    class _Raiser:
        def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
            raise OSError(_errno.EADDRINUSE, "in use")

    monkeypatch.setattr(cli, "OAuthHTTPServer", _Raiser, raising=True)
    with pytest.raises(SystemExit) as ex:
        sys.argv = ["chatmock", "login", "--no-browser"]
        cli.main()
    assert int(ex.value.code) == 13
