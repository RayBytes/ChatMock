"""Test _format_window_duration function in cli module."""

from __future__ import annotations

from chatmock import cli


def test_format_window_duration_none_input() -> None:
    """None input returns None."""
    assert cli._format_window_duration(None) is None


def test_format_window_duration_invalid_type() -> None:
    """Invalid type returns None."""
    assert cli._format_window_duration("invalid") is None


def test_format_window_duration_zero_or_negative() -> None:
    """Zero or negative values return None."""
    assert cli._format_window_duration(0) is None
    assert cli._format_window_duration(-5) is None


def test_format_window_duration_single_minute() -> None:
    """Single minute formatted correctly."""
    assert cli._format_window_duration(1) == "1 minute"


def test_format_window_duration_multiple_minutes() -> None:
    """Multiple minutes formatted correctly."""
    assert cli._format_window_duration(45) == "45 minutes"
    assert cli._format_window_duration(2) == "2 minutes"


def test_format_window_duration_one_hour() -> None:
    """One hour formatted correctly."""
    assert cli._format_window_duration(60) == "1 hour"


def test_format_window_duration_hours_and_minutes() -> None:
    """Hours and minutes formatted correctly."""
    assert cli._format_window_duration(90) == "1 hour 30 minutes"


def test_format_window_duration_one_day() -> None:
    """One day formatted correctly."""
    assert cli._format_window_duration(24 * 60) == "1 day"


def test_format_window_duration_days_hours_minutes() -> None:
    """Days, hours, and minutes formatted correctly."""
    assert cli._format_window_duration(24 * 60 + 90) == "1 day 1 hour 30 minutes"


def test_format_window_duration_one_week() -> None:
    """One week formatted correctly."""
    assert cli._format_window_duration(7 * 24 * 60) == "1 week"


def test_format_window_duration_weeks_days_hours() -> None:
    """Weeks, days, and hours formatted correctly."""
    total = 2 * 7 * 24 * 60 + 3 * 24 * 60 + 5 * 60
    assert cli._format_window_duration(total) == "2 weeks 3 days 5 hours"


def test_format_window_duration_all_units() -> None:
    """All time units formatted correctly."""
    total = 1 * 7 * 24 * 60 + 2 * 24 * 60 + 3 * 60 + 15
    assert cli._format_window_duration(total) == "1 week 2 days 3 hours 15 minutes"


def test_format_window_duration_fallback_branch(monkeypatch: object) -> None:
    """Fallback branch handles unexpected divmod results."""

    def fake_divmod(_value: int, _divisor: int) -> tuple[int, int]:
        return 0, 0

    monkeypatch.setattr(cli, "divmod", fake_divmod, raising=False)
    assert cli._format_window_duration(10) == "10 minutes"


def test_format_reset_duration_none() -> None:
    """None input returns None."""
    assert cli._format_reset_duration(None) is None


def test_format_reset_duration_invalid_type() -> None:
    """Invalid type returns None."""
    assert cli._format_reset_duration("invalid") is None  # type: ignore[arg-type]


def test_format_reset_duration_seconds_under_minute() -> None:
    """Seconds under 1 minute show 'under 1m'."""
    assert cli._format_reset_duration(30) == "under 1m"
    assert cli._format_reset_duration(59) == "under 1m"


def test_format_reset_duration_zero() -> None:
    """Zero seconds shows '0m'."""
    assert cli._format_reset_duration(0) == "0m"


def test_format_reset_duration_minutes() -> None:
    """Minutes formatted correctly."""
    assert cli._format_reset_duration(120) == "2m"


def test_format_reset_duration_hours() -> None:
    """Hours formatted correctly."""
    assert cli._format_reset_duration(3600) == "1h"


def test_format_reset_duration_days() -> None:
    """Days formatted correctly."""
    assert cli._format_reset_duration(86400) == "1d"


def test_format_reset_duration_mixed() -> None:
    """Mixed units formatted correctly (no seconds)."""
    assert cli._format_reset_duration(90060) == "1d 1h 1m"
