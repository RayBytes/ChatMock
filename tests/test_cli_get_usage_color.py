"""Cover _get_usage_color utility function for ANSI color selection."""

from __future__ import annotations

from chatmock.cli import _get_usage_color


def test_get_usage_color_red() -> None:
    """Returns red color code when usage >= 90%."""
    assert _get_usage_color(90.0) == "\033[91m"
    assert _get_usage_color(95.0) == "\033[91m"
    assert _get_usage_color(100.0) == "\033[91m"


def test_get_usage_color_yellow() -> None:
    """Returns yellow color code when 75% <= usage < 90%."""
    assert _get_usage_color(75.0) == "\033[93m"
    assert _get_usage_color(80.0) == "\033[93m"
    assert _get_usage_color(89.9) == "\033[93m"


def test_get_usage_color_blue() -> None:
    """Returns blue color code when 50% <= usage < 75%."""
    assert _get_usage_color(50.0) == "\033[94m"
    assert _get_usage_color(60.0) == "\033[94m"
    assert _get_usage_color(74.9) == "\033[94m"


def test_get_usage_color_green() -> None:
    """Returns green color code when usage < 50%."""
    assert _get_usage_color(0.0) == "\033[92m"
    assert _get_usage_color(25.0) == "\033[92m"
    assert _get_usage_color(49.9) == "\033[92m"
