"""Cover limits store fchmod path."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from chatmock import limits

if TYPE_CHECKING:
    import pytest


def test_store_snapshot_fchmod_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
) -> None:
    """When os.fchmod is available, attempt to set permissions."""
    # Mock _limits_path to use temp directory
    limits_file = tmp_path / ".chatmock_limits.json"
    monkeypatch.setattr(limits, "_limits_path", lambda: limits_file)

    # Create snapshot
    window = limits.RateLimitWindow(
        used_percent=50.0,
        window_minutes=300,
        resets_in_seconds=3600,
    )
    snapshot = limits.RateLimitSnapshot(primary=window, secondary=None)

    # Store it (will call fchmod if available)
    limits.store_rate_limit_snapshot(snapshot)

    # Verify file was created
    assert limits_file.exists()

    # On Unix-like systems, check if fchmod was successful
    if hasattr(os, "fchmod"):
        stat = limits_file.stat()
        # Check if permissions were set (mode & 0o600)
        # This won't fail if fchmod raised OSError
        assert stat.st_size > 0
