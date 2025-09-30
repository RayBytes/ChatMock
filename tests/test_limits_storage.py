"""Tests for limits module storage and loading functions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    import pytest

from chatmock.limits import (
    RateLimitSnapshot,
    RateLimitWindow,
    StoredRateLimitSnapshot,
    compute_reset_at,
    load_rate_limit_snapshot,
    parse_rate_limit_headers,
    record_rate_limits_from_response,
    store_rate_limit_snapshot,
)


def test_parse_rate_limit_headers_exception_handling() -> None:
    """Test parse_rate_limit_headers handles exceptions gracefully."""
    # Malformed headers that trigger exceptions
    bad_headers = Mock()
    bad_headers.get = Mock(side_effect=TypeError("boom"))
    result = parse_rate_limit_headers(bad_headers)
    assert result is None


def test_store_rate_limit_snapshot_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test storing snapshot successfully."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    window = RateLimitWindow(used_percent=50.0, window_minutes=60, resets_in_seconds=300)
    snapshot = RateLimitSnapshot(primary=window, secondary=None)
    captured = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    store_rate_limit_snapshot(snapshot, captured_at=captured)

    limits_file = tmp_path / "usage_limits.json"
    assert limits_file.exists()

    with limits_file.open() as fp:
        data = json.load(fp)

    assert data["captured_at"] == "2025-01-01T12:00:00+00:00"
    assert data["primary"]["used_percent"] == 50.0
    assert data["primary"]["window_minutes"] == 60
    assert data["primary"]["resets_in_seconds"] == 300
    assert "secondary" not in data


def test_store_rate_limit_snapshot_with_secondary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test storing snapshot with both primary and secondary windows."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    primary = RateLimitWindow(used_percent=75.0, window_minutes=60, resets_in_seconds=300)
    secondary = RateLimitWindow(used_percent=25.0, window_minutes=1440, resets_in_seconds=86400)
    snapshot = RateLimitSnapshot(primary=primary, secondary=secondary)

    store_rate_limit_snapshot(snapshot)

    limits_file = tmp_path / "usage_limits.json"
    assert limits_file.exists()

    with limits_file.open() as fp:
        data = json.load(fp)

    assert "primary" in data
    assert "secondary" in data
    assert data["secondary"]["used_percent"] == 25.0


def test_store_rate_limit_snapshot_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test store_rate_limit_snapshot silently ignores OSError."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))
    monkeypatch.setattr("chatmock.limits._limits_path", lambda: Path("/invalid/path/file.json"))

    window = RateLimitWindow(used_percent=50.0, window_minutes=60, resets_in_seconds=300)
    snapshot = RateLimitSnapshot(primary=window, secondary=None)

    # Should not raise
    store_rate_limit_snapshot(snapshot)


def test_load_rate_limit_snapshot_file_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load_rate_limit_snapshot returns None when file doesn't exist."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))
    result = load_rate_limit_snapshot()
    assert result is None


def test_load_rate_limit_snapshot_json_decode_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load_rate_limit_snapshot returns None on invalid JSON."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    limits_file = tmp_path / "usage_limits.json"
    limits_file.write_text("not valid json{}")

    result = load_rate_limit_snapshot()
    assert result is None


def test_load_rate_limit_snapshot_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test load_rate_limit_snapshot returns None on OSError."""
    monkeypatch.setattr("chatmock.limits._limits_path", lambda: Path("/invalid/path/file.json"))
    result = load_rate_limit_snapshot()
    assert result is None


def test_load_rate_limit_snapshot_invalid_captured_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load_rate_limit_snapshot returns None with invalid captured_at."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    limits_file = tmp_path / "usage_limits.json"
    data = {
        "captured_at": "not-a-datetime",
        "primary": {"used_percent": 50.0, "window_minutes": 60, "resets_in_seconds": 300},
    }
    limits_file.write_text(json.dumps(data))

    result = load_rate_limit_snapshot()
    assert result is None


def test_load_rate_limit_snapshot_no_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load_rate_limit_snapshot returns None when no valid windows."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    limits_file = tmp_path / "usage_limits.json"
    data = {
        "captured_at": "2025-01-01T12:00:00+00:00",
        "primary": {"used_percent": None},  # Invalid window
    }
    limits_file.write_text(json.dumps(data))

    result = load_rate_limit_snapshot()
    assert result is None


def test_load_rate_limit_snapshot_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful load of snapshot."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    limits_file = tmp_path / "usage_limits.json"
    data = {
        "captured_at": "2025-01-01T12:00:00+00:00",
        "primary": {"used_percent": 50.0, "window_minutes": 60, "resets_in_seconds": 300},
        "secondary": {"used_percent": 25.0, "window_minutes": 1440, "resets_in_seconds": 86400},
    }
    limits_file.write_text(json.dumps(data))

    result = load_rate_limit_snapshot()

    assert isinstance(result, StoredRateLimitSnapshot)
    assert result.captured_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert result.snapshot.primary is not None
    assert result.snapshot.primary.used_percent == 50.0
    assert result.snapshot.secondary is not None
    assert result.snapshot.secondary.used_percent == 25.0


def test_parse_datetime_non_string() -> None:
    """Test _parse_datetime with non-string input."""
    from chatmock.limits import _parse_datetime

    assert _parse_datetime(123) is None
    assert _parse_datetime(None) is None
    assert _parse_datetime([]) is None


def test_parse_datetime_empty_string() -> None:
    """Test _parse_datetime with empty string."""
    from chatmock.limits import _parse_datetime

    assert _parse_datetime("") is None
    assert _parse_datetime("   ") is None


def test_parse_datetime_z_suffix() -> None:
    """Test _parse_datetime converts Z suffix to +00:00."""
    from chatmock.limits import _parse_datetime

    result = _parse_datetime("2025-01-01T12:00:00Z")
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_datetime_naive_gets_utc() -> None:
    """Test _parse_datetime adds UTC timezone to naive datetime."""
    from chatmock.limits import _parse_datetime

    result = _parse_datetime("2025-01-01T12:00:00")
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_datetime_invalid_format() -> None:
    """Test _parse_datetime returns None for invalid format."""
    from chatmock.limits import _parse_datetime

    assert _parse_datetime("not-a-date") is None
    assert _parse_datetime("2025-99-99") is None


def test_dict_to_window_not_dict() -> None:
    """Test _dict_to_window returns None for non-dict input."""
    from chatmock.limits import _dict_to_window

    assert _dict_to_window("not a dict") is None
    assert _dict_to_window(None) is None
    assert _dict_to_window(123) is None


def test_dict_to_window_missing_used_percent() -> None:
    """Test _dict_to_window returns None when used_percent is missing."""
    from chatmock.limits import _dict_to_window

    assert _dict_to_window({"window_minutes": 60}) is None
    assert _dict_to_window({"used_percent": None}) is None


def test_record_rate_limits_from_response_none() -> None:
    """Test record_rate_limits_from_response handles None response."""
    # Should not raise
    record_rate_limits_from_response(None)


def test_record_rate_limits_from_response_no_headers() -> None:
    """Test record_rate_limits_from_response handles response without headers."""
    response = Mock(spec=[])
    # Should not raise
    record_rate_limits_from_response(response)


def test_record_rate_limits_from_response_no_rate_limit_headers() -> None:
    """Test record_rate_limits_from_response handles response without rate limit headers."""
    response = Mock()
    response.headers = {}
    # Should not raise
    record_rate_limits_from_response(response)


def test_record_rate_limits_from_response_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test record_rate_limits_from_response stores valid headers."""
    monkeypatch.setattr("chatmock.limits.get_home_dir", lambda: str(tmp_path))

    response = Mock()
    response.headers = {
        "x-codex-primary-used-percent": "50.0",
        "x-codex-primary-window-minutes": "60",
        "x-codex-primary-reset-after-seconds": "300",
    }

    record_rate_limits_from_response(response)

    limits_file = tmp_path / "usage_limits.json"
    assert limits_file.exists()


def test_compute_reset_at_none_resets_in_seconds() -> None:
    """Test compute_reset_at returns None when resets_in_seconds is None."""
    captured = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    window = RateLimitWindow(used_percent=50.0, window_minutes=60, resets_in_seconds=None)

    result = compute_reset_at(captured, window)
    assert result is None


def test_compute_reset_at_success() -> None:
    """Test compute_reset_at computes correct reset time."""
    captured = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    window = RateLimitWindow(used_percent=50.0, window_minutes=60, resets_in_seconds=300)

    result = compute_reset_at(captured, window)

    assert result is not None
    assert result == datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc)


def test_compute_reset_at_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test compute_reset_at handles exceptions gracefully."""
    captured = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    window = RateLimitWindow(used_percent=50.0, window_minutes=60, resets_in_seconds=300)

    # Patch timedelta to raise an exception
    import chatmock.limits

    def broken_timedelta(*_args, **_kwargs):
        raise ValueError("timedelta error")

    monkeypatch.setattr(chatmock.limits, "timedelta", broken_timedelta)

    result = compute_reset_at(captured, window)
    assert result is None
