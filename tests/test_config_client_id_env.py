"""Tests for config CLIENT_ID_DEFAULT environment override."""

from __future__ import annotations

import importlib


def test_client_id_default_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Environment variable overrides CLIENT_ID_DEFAULT."""
    monkeypatch.setenv("CHATGPT_LOCAL_CLIENT_ID", "id_123")
    # Reload module to re-evaluate constants
    mod = importlib.import_module("chatmock.config")
    mod = importlib.reload(mod)
    assert mod.CLIENT_ID_DEFAULT == "id_123"
