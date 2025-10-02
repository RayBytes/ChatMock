"""Cover _now_iso8601 utility function for ISO 8601 timestamp generation."""

from __future__ import annotations

from chatmock.utils import _now_iso8601


def test_now_iso8601_format() -> None:
    """Returns ISO 8601 formatted timestamp with Z suffix."""
    result = _now_iso8601()
    # Should be a string
    assert isinstance(result, str)
    # Should end with Z
    assert result.endswith("Z")
    # Should contain T separator
    assert "T" in result
    # Should not contain +00:00 (replaced with Z)
    assert "+00:00" not in result


def test_now_iso8601_parseable() -> None:
    """Generated timestamp is parseable as ISO 8601."""
    import datetime

    result = _now_iso8601()
    # Should be parseable back to datetime
    # Replace Z with +00:00 for parsing
    parsed = datetime.datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
