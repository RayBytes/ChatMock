"""Cover load_chatgpt_tokens with ensure_fresh token refresh logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chatmock import utils

if TYPE_CHECKING:
    import pytest


def test_load_chatgpt_tokens_ensure_fresh_refresh_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ensure_fresh=True and token needs refresh, perform refresh."""
    auth_data = {
        "tokens": {
            "access_token": "old_access",
            "refresh_token": "valid_refresh",
            "id_token": "old_id",
        },
        "last_refresh": "2020-01-01T00:00:00Z",
    }

    refreshed_tokens = {
        "access_token": "new_access",
        "id_token": "new_id",
        "refresh_token": "new_refresh",
        "account_id": "test_account",
    }

    # Mock functions
    monkeypatch.setattr(utils, "read_auth_file", lambda: auth_data)
    monkeypatch.setattr(utils, "_should_refresh_access_token", lambda _, __: True)
    monkeypatch.setattr(utils, "_refresh_chatgpt_tokens", lambda _, __: refreshed_tokens)
    monkeypatch.setattr(
        utils,
        "_persist_refreshed_auth",
        lambda auth, tokens: (auth, tokens),
    )

    access, account_id, id_token = utils.load_chatgpt_tokens(ensure_fresh=True)

    # Should return refreshed tokens
    test_id = "new_id"
    assert access == "new_access"
    assert account_id == "test_account"
    assert id_token == test_id


def test_load_chatgpt_tokens_ensure_fresh_persist_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When persist fails, still return updated tokens in memory."""
    auth_data = {
        "tokens": {
            "access_token": "old_access",
            "refresh_token": "valid_refresh",
            "id_token": "old_id",
        },
        "last_refresh": "2020-01-01T00:00:00Z",
    }

    refreshed_tokens = {
        "access_token": "new_access",
        "id_token": "new_id",
        "refresh_token": "new_refresh",
        "account_id": "test_account",
    }

    # Mock persist to fail
    monkeypatch.setattr(utils, "read_auth_file", lambda: auth_data)
    monkeypatch.setattr(utils, "_should_refresh_access_token", lambda _, __: True)
    monkeypatch.setattr(utils, "_refresh_chatgpt_tokens", lambda _, __: refreshed_tokens)
    monkeypatch.setattr(utils, "_persist_refreshed_auth", lambda _, __: None)

    access, _account_id, _id_token = utils.load_chatgpt_tokens(ensure_fresh=True)

    # Should still have new tokens in memory
    assert access == "new_access"
