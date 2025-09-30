"""Test parsing functions in limits module."""

from __future__ import annotations

import math

from chatmock import limits


def test_parse_float_none_input() -> None:
    """None input returns None."""
    assert limits._parse_float(None) is None  # noqa: SLF001


def test_parse_float_int_value() -> None:
    """Integer value converted to float."""
    assert limits._parse_float(42) == 42.0  # noqa: SLF001


def test_parse_float_float_value() -> None:
    """Float value returned as-is."""
    assert limits._parse_float(3.14) == 3.14  # noqa: SLF001


def test_parse_float_string_value() -> None:
    """String value parsed to float."""
    assert limits._parse_float("123.45") == 123.45  # noqa: SLF001


def test_parse_float_empty_string() -> None:
    """Empty string returns None."""
    assert limits._parse_float("") is None  # noqa: SLF001
    assert limits._parse_float("   ") is None  # noqa: SLF001


def test_parse_float_nan_string() -> None:
    """NaN string returns None."""
    assert limits._parse_float("nan") is None  # noqa: SLF001
    assert limits._parse_float("NaN") is None  # noqa: SLF001


def test_parse_float_inf_string() -> None:
    """Infinity string returns None."""
    assert limits._parse_float("inf") is None  # noqa: SLF001
    assert limits._parse_float("-inf") is None  # noqa: SLF001


def test_parse_float_invalid_string() -> None:
    """Invalid string returns None."""
    assert limits._parse_float("not_a_number") is None  # noqa: SLF001


def test_parse_int_none_input() -> None:
    """None input returns None."""
    assert limits._parse_int(None) is None  # noqa: SLF001


def test_parse_int_bool_value() -> None:
    """Boolean value returns None (to avoid bool-as-int coercion)."""
    assert limits._parse_int(True) is None  # noqa: SLF001
    assert limits._parse_int(False) is None  # noqa: SLF001


def test_parse_int_int_value() -> None:
    """Integer value returned as-is."""
    assert limits._parse_int(42) == 42  # noqa: SLF001


def test_parse_int_string_value() -> None:
    """String value parsed to int."""
    assert limits._parse_int("123") == 123  # noqa: SLF001


def test_parse_int_empty_string() -> None:
    """Empty string returns None."""
    assert limits._parse_int("") is None  # noqa: SLF001
    assert limits._parse_int("   ") is None  # noqa: SLF001


def test_parse_int_invalid_string() -> None:
    """Invalid string returns None."""
    assert limits._parse_int("not_a_number") is None  # noqa: SLF001


def test_parse_int_float_string() -> None:
    """Float string cannot be parsed as int."""
    assert limits._parse_int("3.14") is None  # noqa: SLF001


def test_parse_window_missing_used_percent() -> None:
    """Missing used percent returns None."""
    headers = {"window": 60, "reset": 300}
    result = limits._parse_window(  # noqa: SLF001
        headers, "used", "window", "reset"
    )
    assert result is None


def test_parse_window_valid_all_fields() -> None:
    """All fields present and valid."""
    headers = {"used": 45.5, "window": 60, "reset": 300}
    result = limits._parse_window(  # noqa: SLF001
        headers, "used", "window", "reset"
    )
    assert result is not None
    assert result.used_percent == 45.5
    assert result.window_minutes == 60
    assert result.resets_in_seconds == 300


def test_parse_window_only_used_percent() -> None:
    """Only used percent present."""
    headers = {"used": 75.0}
    result = limits._parse_window(  # noqa: SLF001
        headers, "used", "window", "reset"
    )
    assert result is not None
    assert result.used_percent == 75.0
    assert result.window_minutes is None
    assert result.resets_in_seconds is None