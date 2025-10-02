"""Tests for chatmock.cli info subcommand output paths."""

from __future__ import annotations

import io
import sys

import pytest

from chatmock import cli


def _run_main(argv: list[str]) -> str:
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        sys.argv = ["chatmock", *argv]
        with pytest.raises(SystemExit):
            cli.main()
    finally:
        sys.stdout = old
    return buf.getvalue()


def test_cli_info_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Emit JSON when --json is passed."""
    monkeypatch.setattr(cli, "read_auth_file", lambda: {"ok": True}, raising=True)
    out = _run_main(["info", "--json"]).strip()
    assert out.startswith("{")
    assert "\n" in out


def test_cli_info_not_signed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Show helpful message when not signed in."""
    monkeypatch.setattr(cli, "read_auth_file", lambda: None, raising=True)
    monkeypatch.setattr(cli, "load_chatgpt_tokens", lambda: (None, None, None), raising=True)
    out = _run_main(["info"])  # human-readable output
    assert "Not signed in" in out
    assert "Run: python3 chatmock.py login" in out


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_cli_info_signed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretty-print claims when signed in."""
    # synthesize id/access tokens with expected claims
    id_payload = {"email": "u@example.com"}
    access_payload = {"https://api.openai.com/auth": {"chatgpt_plan_type": "plus"}}
    id_token = f"{_b64url(b'{}')}.{_b64url(__import__('json').dumps(id_payload).encode())}."
    access_token = f"{_b64url(b'{}')}.{_b64url(__import__('json').dumps(access_payload).encode())}."

    monkeypatch.setattr(cli, "read_auth_file", lambda: {"tokens": {}}, raising=True)
    monkeypatch.setattr(
        cli, "load_chatgpt_tokens", lambda: (access_token, "acc_1", id_token), raising=True
    )
    out = _run_main(["info"])  # human-readable output
    assert "Signed in with ChatGPT" in out
    assert "Plan: Plus" in out
    assert "Account ID: acc_1" in out


def test_cmd_serve_invokes_app_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_serve should construct app and run it."""

    class _App:
        def __init__(self) -> None:
            self.ran = False

        def run(self, **_kwargs: object) -> None:  # type: ignore[no-untyped-def]
            self.ran = True

    fake = _App()
    monkeypatch.setattr(cli, "create_app", lambda **_kw: fake, raising=True)
    rc = cli.cmd_serve(
        host="127.0.0.1",
        port=0,
        verbose=False,
        reasoning_effort="medium",
        reasoning_summary="auto",
        reasoning_compat="think-tags",
        debug_model=None,
        expose_reasoning_models=False,
        default_web_search=False,
    )
    assert rc == 0
    assert fake.ran


def test_main_serve_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() should route to serve path."""

    class _App:
        def run(self, **_kwargs: object) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(cli, "create_app", lambda **_kw: _App(), raising=True)
    # We don't assert output; just ensure SystemExit is raised via sys.exit
    _ = _run_main(["serve", "--port", "0"])
