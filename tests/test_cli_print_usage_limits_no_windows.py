"""Cover _print_usage_limits_block when data exists but no windows."""

from __future__ import annotations

import datetime
from typing import NamedTuple

from chatmock import cli


class MockSnapshot(NamedTuple):
    """Mock rate limit snapshot."""

    primary: None = None
    secondary: None = None


class MockStored(NamedTuple):
    """Mock stored rate limit data."""

    snapshot: MockSnapshot
    captured_at: datetime.datetime


def test_print_usage_limits_no_windows(monkeypatch: object, capsys: object) -> None:
    """When rate limit data exists but no windows, print appropriate message."""
    # Create mock stored data with no windows
    stored = MockStored(
        snapshot=MockSnapshot(),
        captured_at=datetime.datetime.now(datetime.timezone.utc),
    )

    # Mock load_rate_limit_snapshot to return our mock
    monkeypatch.setattr(cli, "load_rate_limit_snapshot", lambda: stored)

    # Call the function
    cli._print_usage_limits_block()

    # Capture stdout
    captured = capsys.readouterr()

    # Verify the output contains the "no windows" message
    assert "Usage data was captured" in captured.out
    assert "no limit windows were provided" in captured.out
    assert "📊 Usage Limits" in captured.out
