"""Tests for token helpers when no auth present."""

from __future__ import annotations

from chatmock import utils


def test_load_chatgpt_tokens_none(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(utils, "read_auth_file", lambda: None, raising=True)
    assert utils.load_chatgpt_tokens() == (None, None, None)
