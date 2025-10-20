"""Cover _derive_account_id when id_token is empty or None."""

from __future__ import annotations

from chatmock.utils import _derive_account_id


def test_derive_account_id_none() -> None:
    """When id_token is None, return None."""
    result = _derive_account_id(None)
    assert result is None


def test_derive_account_id_empty_string() -> None:
    """When id_token is empty string, return None."""
    result = _derive_account_id("")
    assert result is None
