"""Test CLI info plan mapping fallback for unknown plan types."""

from __future__ import annotations

import io
import sys

import pytest

from chatmock import cli


def test_cli_info_unknown_plan_title_case(monkeypatch: pytest.MonkeyPatch) -> None:
    def parse(token: str):  # type: ignore[no-untyped-def]
        if token == "id":
            return {"email": "u@example.com"}
        return {"https://api.openai.com/auth": {"chatgpt_plan_type": "weird"}}

    monkeypatch.setattr(cli, "read_auth_file", lambda: {"tokens": {}}, raising=True)
    monkeypatch.setattr(cli, "load_chatgpt_tokens", lambda: ("a", "acc_1", "id"), raising=True)
    monkeypatch.setattr(cli, "parse_jwt_claims", parse, raising=True)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        with pytest.raises(SystemExit):
            sys.argv = ["chatmock", "info"]
            cli.main()
    finally:
        sys.stdout = old
    out = buf.getvalue()
    assert "Plan: Weird" in out
