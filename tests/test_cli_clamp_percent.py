"""Cover _clamp_percent utility function edge cases."""

from __future__ import annotations

import math

from chatmock.cli import _clamp_percent


def test_clamp_percent_valid() -> None:
    """Valid percentages are returned unchanged."""
    assert _clamp_percent(0.0) == 0.0
    assert _clamp_percent(50.0) == 50.0
    assert _clamp_percent(100.0) == 100.0


def test_clamp_percent_below_min() -> None:
    """Percentages below 0 are clamped to 0."""
    assert _clamp_percent(-1.0) == 0.0
    assert _clamp_percent(-100.0) == 0.0


def test_clamp_percent_above_max() -> None:
    """Percentages above 100 are clamped to 100."""
    assert _clamp_percent(101.0) == 100.0
    assert _clamp_percent(200.0) == 100.0


def test_clamp_percent_nan() -> None:
    """NaN values return 0."""
    assert _clamp_percent(math.nan) == 0.0


def test_clamp_percent_non_numeric() -> None:
    """Non-numeric values return 0."""
    assert _clamp_percent("not a number") == 0.0
    assert _clamp_percent(None) == 0.0
    assert _clamp_percent([]) == 0.0
    assert _clamp_percent({}) == 0.0
