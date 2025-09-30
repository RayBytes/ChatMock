"""Cover reset display branches in _print_usage_limits_block."""

from __future__ import annotations

import datetime
from typing import NamedTuple


class MockWindow(NamedTuple):
    """Mock rate limit window."""

    used_percent: float = 50.0
    window_minutes: int | None = 300
    resets_in_seconds: int | None = None


class MockSnapshot(NamedTuple):
    """Mock rate limit snapshot."""

    primary: MockWindow | None = None
    secondary: None = None


class MockStored(NamedTuple):
    """Mock stored rate limit data."""

    snapshot: MockSnapshot
    captured_at: datetime.datetime


def test_print_usage_limits_reset_in_only(monkeypatch: object, capsys: object) -> None:
    """Test reset display when only reset_in is available."""
    from chatmock import cli

    # Create window with resets_in but mock compute_reset_at to return None
    window = MockWindow(resets_in_seconds=3600)
    stored = MockStored(
        snapshot=MockSnapshot(primary=window),
        captured_at=datetime.datetime.now(datetime.timezone.utc),
    )

    monkeypatch.setattr(cli, "load_rate_limit_snapshot", lambda: stored)
    monkeypatch.setattr(cli, "compute_reset_at", lambda *_: None)

    cli._print_usage_limits_block()
    captured = capsys.readouterr()

    # Should show "Resets in:" without "at"
    assert "Resets in:" in captured.out
    assert "Resets at:" not in captured.out


def test_print_usage_limits_reset_at_only(monkeypatch: object, capsys: object) -> None:
    """Test reset display when only reset_at is available."""
    from chatmock import cli

    # Create window with no resets_in
    window = MockWindow(resets_in_seconds=None)
    stored = MockStored(
        snapshot=MockSnapshot(primary=window),
        captured_at=datetime.datetime.now(datetime.timezone.utc),
    )

    reset_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    monkeypatch.setattr(cli, "load_rate_limit_snapshot", lambda: stored)
    monkeypatch.setattr(cli, "compute_reset_at", lambda *_: reset_time)
    monkeypatch.setattr(cli, "_format_reset_duration", lambda _: None)

    cli._print_usage_limits_block()
    captured = capsys.readouterr()

    # Should show "Resets at:" without "in"
    assert "Resets at:" in captured.out
    assert captured.out.count("Resets in:") == 0
