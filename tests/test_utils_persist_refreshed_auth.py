"""Cover _persist_refreshed_auth function."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chatmock import utils

if TYPE_CHECKING:
    import pytest


def test_persist_refreshed_auth_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When write succeeds, return updated auth and tokens."""
    auth = {"tokens": {"old": "token"}}
    updated_tokens = {"new": "token"}

    # Mock write_auth_file to succeed
    monkeypatch.setattr(utils, "write_auth_file", lambda _: True)
    # Mock _now_iso8601 to return predictable timestamp
    monkeypatch.setattr(utils, "_now_iso8601", lambda: "2025-01-01T00:00:00Z")

    result = utils._persist_refreshed_auth(auth, updated_tokens)
    assert result is not None
    updated_auth, tokens = result
    assert updated_auth["tokens"] == updated_tokens
    assert updated_auth["last_refresh"] == "2025-01-01T00:00:00Z"
    assert tokens == updated_tokens


def test_persist_refreshed_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """When write fails, return None."""
    auth = {"tokens": {"old": "token"}}
    updated_tokens = {"new": "token"}

    # Mock write_auth_file to fail
    monkeypatch.setattr(utils, "write_auth_file", lambda _: False)

    result = utils._persist_refreshed_auth(auth, updated_tokens)
    assert result is None
