"""Tests for config fallback behavior when prompt files are missing."""

from __future__ import annotations

from chatmock import config


def test_read_gpt5_codex_instructions_uses_fallback(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(config, "_read_prompt_text", lambda filename: None, raising=True)
    out = config.read_gpt5_codex_instructions("FALLBACK")
    assert out == "FALLBACK"
