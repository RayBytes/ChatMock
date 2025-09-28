"""Tests for config base instructions missing path."""

from __future__ import annotations

import pytest

from chatmock import config


def test_read_base_instructions_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "_read_prompt_text", lambda filename: None, raising=True)
    with pytest.raises(FileNotFoundError):
        config.read_base_instructions()
