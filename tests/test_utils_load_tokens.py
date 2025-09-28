"""Tests for token loading helpers in chatmock.utils."""

from __future__ import annotations

from chatmock import utils


def test_load_chatgpt_tokens_reads_from_auth(monkeypatch: object) -> None:
    fake = {"tokens": {"access_token": "a", "account_id": "b", "id_token": "c"}}
    monkeypatch.setattr = monkeypatch.setattr  # appease type checker
    monkeypatch.setattr(utils, "read_auth_file", lambda: fake, raising=True)  # type: ignore[attr-defined]
    access, account, idt = utils.load_chatgpt_tokens()
    assert (access, account, idt) == ("a", "b", "c")
