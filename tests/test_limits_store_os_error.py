"""Test limits.py OSError suppression in fchmod."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def test_store_rate_limit_snapshot_fchmod_oserror(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Test that OSError in fchmod is suppressed (lines 150-151)."""
    from chatmock import limits

    # Mock _limits_path to return tmp_path file
    limits_file = tmp_path / "limits.json"  # type: ignore[operator]
    monkeypatch.setattr(limits, "_limits_path", lambda: limits_file)

    # Create a mock snapshot
    from chatmock.limits import RateLimitSnapshot, RateLimitWindow

    window = RateLimitWindow(
        used_percent=50.0,
        window_minutes=60,
        resets_in_seconds=3600,
    )
    snapshot = RateLimitSnapshot(primary=window, secondary=None)

    # Mock fchmod to raise OSError
    original_fchmod = getattr(os, "fchmod", None)

    def mock_fchmod(fd: int, mode: int) -> None:
        raise OSError("fchmod failed")

    if original_fchmod is not None:
        monkeypatch.setattr(os, "fchmod", mock_fchmod)

    # Should not raise despite fchmod error
    limits.store_rate_limit_snapshot(snapshot)

    # Verify file was still written
    assert limits_file.exists()
    with limits_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["primary"]["used_percent"] == 50.0
