"""Tests for model name normalization, with minimal Flask stub."""

from __future__ import annotations

import sys
import types

# Provide a very small stub for 'flask' so the module under test can import.
_flask = types.ModuleType("flask")
_flask.Response = object  # type: ignore[attr-defined]


def _noop(*args: object, **kwargs: object) -> None:
    """No-op stub used to satisfy import-time attributes."""
    del args, kwargs


_flask.jsonify = _noop  # type: ignore[assignment]
_flask.make_response = _noop  # type: ignore[assignment]
_flask.request = types.SimpleNamespace(headers={})
sys.modules.setdefault("flask", _flask)

from chatmock.upstream import normalize_model_name


def test_normalize_model_name_aliases() -> None:
    """Aliases and effort suffixes normalize to canonical names."""
    assert normalize_model_name("gpt5") == "gpt-5"
    assert normalize_model_name("gpt-5-latest") == "gpt-5"
    assert normalize_model_name("gpt-5-medium") == "gpt-5"
    assert normalize_model_name("gpt-5_high") == "gpt-5"
    assert normalize_model_name("codex") == "codex-mini-latest"
    assert normalize_model_name("codex-mini") == "codex-mini-latest"


def test_normalize_model_name_debug_override() -> None:
    """Debug model overrides requested name."""
    assert normalize_model_name("anything", debug_model="forced") == "forced"
