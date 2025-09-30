"""Cover _parse_iso8601 utility function for ISO 8601 datetime parsing."""

from __future__ import annotations

import datetime

from chatmock.utils import _parse_iso8601


def test_parse_iso8601_with_z_suffix() -> None:
    """Parse ISO 8601 string with Z suffix."""
    result = _parse_iso8601("2025-09-30T12:00:00Z")
    assert result is not None
    assert result.tzinfo == datetime.timezone.utc


def test_parse_iso8601_with_utc_offset() -> None:
    """Parse ISO 8601 string with UTC offset."""
    result = _parse_iso8601("2025-09-30T12:00:00+00:00")
    assert result is not None
    assert result.tzinfo == datetime.timezone.utc


def test_parse_iso8601_naive_datetime() -> None:
    """Parse naive datetime (no timezone) - should add UTC."""
    result = _parse_iso8601("2025-09-30T12:00:00")
    assert result is not None
    assert result.tzinfo == datetime.timezone.utc


def test_parse_iso8601_with_different_offset() -> None:
    """Parse ISO 8601 string with non-UTC offset."""
    result = _parse_iso8601("2025-09-30T12:00:00+05:30")
    assert result is not None
    # Should be converted to UTC
    assert result.tzinfo == datetime.timezone.utc


def test_parse_iso8601_invalid_format() -> None:
    """Invalid format returns None."""
    assert _parse_iso8601("not-a-date") is None
    assert _parse_iso8601("2025-99-99") is None


def test_parse_iso8601_none_input() -> None:
    """None input returns None."""
    assert _parse_iso8601(None) is None  # type: ignore[arg-type]


def test_parse_iso8601_non_string_input() -> None:
    """Non-string input returns None."""
    assert _parse_iso8601(12345) is None  # type: ignore[arg-type]
    assert _parse_iso8601([]) is None  # type: ignore[arg-type]
