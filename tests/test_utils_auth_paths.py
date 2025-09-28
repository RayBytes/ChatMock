"""Additional tests for auth token helpers to cover branches."""

from __future__ import annotations

from chatmock import utils


def test_get_effective_chatgpt_auth_uses_existing_account_id(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(utils, "load_chatgpt_tokens", lambda: ("a", "acc", None), raising=True)
    access, account = utils.get_effective_chatgpt_auth()
    assert access == "a" and account == "acc"
