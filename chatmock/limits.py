from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

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
    used_percent: float
    window_minutes: int | None
    resets_in_seconds: int | None


@dataclass
class RateLimitSnapshot:
    primary: RateLimitWindow | None
    secondary: RateLimitWindow | None


@dataclass
class StoredRateLimitSnapshot:
    captured_at: datetime
    snapshot: RateLimitSnapshot


def _parse_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        value_str = str(value).strip()
        if not value_str:
            return None
        parsed = float(value_str)
        if not (parsed == parsed and parsed not in (float("inf"), float("-inf"))):
            return None
        return parsed
    except Exception:
        return None


def _parse_int(value: Any) -> int | None:
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
    except Exception:
        return None


def _parse_window(headers: Mapping[str, Any], used_key: str, window_key: str, reset_key: str) -> RateLimitWindow | None:
    used_percent = _parse_float(headers.get(used_key))
    if used_percent is None:
        return None
    window_minutes = _parse_int(headers.get(window_key))
    resets_in_seconds = _parse_int(headers.get(reset_key))
    return RateLimitWindow(used_percent=used_percent, window_minutes=window_minutes, resets_in_seconds=resets_in_seconds)


def parse_rate_limit_headers(headers: Mapping[str, Any]) -> RateLimitSnapshot | None:
    try:
        primary = _parse_window(headers, _PRIMARY_USED, _PRIMARY_WINDOW, _PRIMARY_RESET)
        secondary = _parse_window(headers, _SECONDARY_USED, _SECONDARY_WINDOW, _SECONDARY_RESET)
        if primary is None and secondary is None:
            return None
        return RateLimitSnapshot(primary=primary, secondary=secondary)
    except Exception:
        return None


def _limits_path() -> str:
    home = get_home_dir()
    return os.path.join(home, _LIMITS_FILENAME)


def store_rate_limit_snapshot(snapshot: RateLimitSnapshot, captured_at: datetime | None = None) -> None:
    captured = captured_at or datetime.now(timezone.utc)
    try:
        home = get_home_dir()
        os.makedirs(home, exist_ok=True)
        payload: dict[str, Any] = {
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
        with open(_limits_path(), "w", encoding="utf-8") as fp:
            if hasattr(os, "fchmod"):
                try:
                    os.fchmod(fp.fileno(), 0o600)
                except OSError:
                    pass
            json.dump(payload, fp, indent=2)
    except Exception:
        # Silently ignore persistence errors.
        pass


def load_rate_limit_snapshot() -> StoredRateLimitSnapshot | None:
    try:
        with open(_limits_path(), encoding="utf-8") as fp:
            raw = json.load(fp)
    except FileNotFoundError:
        return None
    except Exception:
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


def _parse_datetime(value: Any) -> datetime | None:
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
        return dt
    except ValueError:
        return None


def _dict_to_window(value: Any) -> RateLimitWindow | None:
    if not isinstance(value, dict):
        return None
    used = _parse_float(value.get("used_percent"))
    if used is None:
        return None
    window = _parse_int(value.get("window_minutes"))
    resets = _parse_int(value.get("resets_in_seconds"))
    return RateLimitWindow(used_percent=used, window_minutes=window, resets_in_seconds=resets)


def record_rate_limits_from_response(response: Any) -> None:
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
    if window.resets_in_seconds is None:
        return None
    try:
        return captured_at + timedelta(seconds=int(window.resets_in_seconds))
    except Exception:
        return None

