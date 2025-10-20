"""Cover _render_progress_bar utility function."""

from __future__ import annotations

from chatmock.cli import _render_progress_bar


def test_render_progress_bar_empty() -> None:
    """Empty bar at 0%."""
    result = _render_progress_bar(0.0)
    assert result.startswith("[")
    assert result.endswith("]")


def test_render_progress_bar_full() -> None:
    """Full bar at 100%."""
    result = _render_progress_bar(100.0)
    assert result.startswith("[")
    assert result.endswith("]")


def test_render_progress_bar_partial() -> None:
    """Partial bar at 50%."""
    result = _render_progress_bar(50.0)
    assert result.startswith("[")
    assert result.endswith("]")


def test_render_progress_bar_small_value() -> None:
    """Bar with small percentage."""
    result = _render_progress_bar(1.0)
    assert result.startswith("[")
    assert result.endswith("]")
