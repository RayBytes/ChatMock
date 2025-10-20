"""Utilities for parsing, storing, and computing usage rate limits."""

from __future__ import annotations

import contextlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

from .utils import get_home_dir

_PRIMARY_USED = "x-codex-primary-used-percent"
_PRIMARY_WINDOW = "x-codex-primary-window-minutes"
_PRIMARY_RESET = "x-codex-primary-reset-after-seconds"
_SECONDARY_USED = "x-codex-secondary-used-percent"
_SECONDARY_WINDOW = "x-codex-secondary-window-minutes"
_SECONDARY_RESET = "x-codex-secondary-reset-after-seconds"

_LIMITS_FILENAME = "usage_limits.json"


@dataclass
class RateLimitWindow:
    """Represents a single rate-limit window."""

    used_percent: float
    window_minutes: int | None
    resets_in_seconds: int | None


@dataclass
class RateLimitSnapshot:
    """Pair of primary/secondary rate-limit windows parsed from headers."""

    primary: RateLimitWindow | None
    secondary: RateLimitWindow | None


@dataclass
class StoredRateLimitSnapshot:
    """On-disk snapshot with capture timestamp."""

    captured_at: datetime
    snapshot: RateLimitSnapshot


def _parse_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        value_str = str(value).strip()
        if not value_str:
            return None
        parsed = float(value_str)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
    except (TypeError, ValueError):
        return None
    else:
        return parsed


def _parse_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        value_str = str(value).strip()
        if not value_str:
            return None
        return int(value_str)
    except (TypeError, ValueError):
        return None


def _parse_window(
    headers: Mapping[str, object], used_key: str, window_key: str, reset_key: str
) -> RateLimitWindow | None:
    used_percent = _parse_float(headers.get(used_key))
    if used_percent is None:
        return None
    window_minutes = _parse_int(headers.get(window_key))
    resets_in_seconds = _parse_int(headers.get(reset_key))
    return RateLimitWindow(
        used_percent=used_percent,
        window_minutes=window_minutes,
        resets_in_seconds=resets_in_seconds,
    )


def parse_rate_limit_headers(headers: Mapping[str, object]) -> RateLimitSnapshot | None:
    """
    Parse custom rate-limit headers into a snapshot.

    Returns None if no usable windows were found.
    """
    try:
        primary = _parse_window(headers, _PRIMARY_USED, _PRIMARY_WINDOW, _PRIMARY_RESET)
        secondary = _parse_window(headers, _SECONDARY_USED, _SECONDARY_WINDOW, _SECONDARY_RESET)
        if primary is None and secondary is None:
            return None
        return RateLimitSnapshot(primary=primary, secondary=secondary)
    except (TypeError, ValueError):
        return None


def _limits_path() -> Path:
    """Return absolute path to the limits snapshot file."""
    home = Path(get_home_dir())
    return home / _LIMITS_FILENAME


def store_rate_limit_snapshot(
    snapshot: RateLimitSnapshot, captured_at: datetime | None = None
) -> None:
    """Persist a snapshot to disk; failures are ignored."""
    captured = captured_at or datetime.now(timezone.utc)
    home = Path(get_home_dir())
    home.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "captured_at": captured.isoformat(),
    }
    if snapshot.primary:
        payload["primary"] = {
            "used_percent": snapshot.primary.used_percent,
            "window_minutes": snapshot.primary.window_minutes,
            "resets_in_seconds": snapshot.primary.resets_in_seconds,
        }
    if snapshot.secondary:
        payload["secondary"] = {
            "used_percent": snapshot.secondary.used_percent,
            "window_minutes": snapshot.secondary.window_minutes,
            "resets_in_seconds": snapshot.secondary.resets_in_seconds,
        }
    try:
        with _limits_path().open("w", encoding="utf-8") as fp:
            if hasattr(os, "fchmod"):  # pragma: no branch
                with contextlib.suppress(OSError):
                    os.fchmod(fp.fileno(), 0o600)
            json.dump(payload, fp, indent=2)
    except (OSError, TypeError, ValueError):
        # Silently ignore persistence errors.
        return


def load_rate_limit_snapshot() -> StoredRateLimitSnapshot | None:
    """Load a previously stored snapshot, if present and valid."""
    try:
        with _limits_path().open(encoding="utf-8") as fp:
            raw = json.load(fp)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None

    captured_raw = raw.get("captured_at")
    captured_at = _parse_datetime(captured_raw)
    if captured_at is None:
        return None

    snapshot = RateLimitSnapshot(
        primary=_dict_to_window(raw.get("primary")),
        secondary=_dict_to_window(raw.get("secondary")),
    )
    if snapshot.primary is None and snapshot.secondary is None:
        return None
    return StoredRateLimitSnapshot(captured_at=captured_at, snapshot=snapshot)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    else:
        return dt


def _dict_to_window(value: object) -> RateLimitWindow | None:
    if not isinstance(value, dict):
        return None
    used = _parse_float(value.get("used_percent"))
    if used is None:
        return None
    window = _parse_int(value.get("window_minutes"))
    resets = _parse_int(value.get("resets_in_seconds"))
    return RateLimitWindow(used_percent=used, window_minutes=window, resets_in_seconds=resets)


def record_rate_limits_from_response(response: object) -> None:
    """Best-effort extraction of rate-limit headers from an upstream response."""
    if response is None:
        return
    headers = getattr(response, "headers", None)
    if headers is None:
        return
    snapshot = parse_rate_limit_headers(headers)
    if snapshot is None:
        return
    store_rate_limit_snapshot(snapshot)


def compute_reset_at(captured_at: datetime, window: RateLimitWindow) -> datetime | None:
    """Compute when a window resets based on captured_at and seconds-to-reset."""
    if window.resets_in_seconds is None:
        return None
    try:
        return captured_at + timedelta(seconds=int(window.resets_in_seconds))
    except (TypeError, ValueError):
        return None
