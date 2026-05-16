from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS = 1000
_LOCK = threading.Lock()


class ResponsesWebsocketSessionConflictError(RuntimeError):
    pass


class ResponsesWebsocketSessionCapacityError(RuntimeError):
    pass


class ResponsesWebsocketSessionNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetainedUpstreamWebsocketLease:
    response_id: str | None
    upstream_ws: Any
    created: bool


@dataclass
class _RetainedUpstreamWebsocketEntry:
    upstream_ws: Any
    in_use: bool
    last_used: float


_SESSIONS: OrderedDict[str, _RetainedUpstreamWebsocketEntry] = OrderedDict()
_ANONYMOUS_LEASES: dict[int, Any] = {}


def _close_upstream_websocket(upstream_ws: Any) -> None:
    try:
        upstream_ws.close()
    except Exception:
        pass


def _normalize_max_sessions(max_sessions: int) -> int:
    if not isinstance(max_sessions, int):
        return DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS
    return max(1, max_sessions)


def _is_upstream_websocket_marked_closed(upstream_ws: Any) -> bool:
    try:
        if bool(getattr(upstream_ws, "closed", False)):
            return True
    except Exception:
        pass
    try:
        if getattr(upstream_ws, "close_code", None) is not None:
            return True
    except Exception:
        pass
    return False


def _close_entry_locked(response_id: str) -> None:
    entry = _SESSIONS.pop(response_id, None)
    if entry is None:
        return
    _close_upstream_websocket(entry.upstream_ws)


def _evict_closed_entries_locked() -> None:
    for response_id, entry in list(_SESSIONS.items()):
        if entry.in_use:
            continue
        if _is_upstream_websocket_marked_closed(entry.upstream_ws):
            _close_entry_locked(response_id)


def _active_session_count_locked() -> int:
    return len(_SESSIONS) + len(_ANONYMOUS_LEASES)


def _evict_to_capacity_locked(max_sessions: int) -> None:
    _evict_closed_entries_locked()
    while _active_session_count_locked() >= max_sessions:
        evicted = False
        for response_id, entry in list(_SESSIONS.items()):
            if entry.in_use:
                continue
            _close_entry_locked(response_id)
            evicted = True
            break
        if not evicted:
            raise ResponsesWebsocketSessionCapacityError(
                "Too many retained upstream websocket sessions are active right now."
            )


def _normalize_response_id(response_id: str | None) -> str | None:
    if not isinstance(response_id, str):
        return None
    normalized = response_id.strip()
    return normalized or None


def acquire_retained_upstream_websocket(
    response_id: str | None,
    create_upstream_websocket: Callable[[], Any],
    *,
    max_sessions: int = DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS,
) -> RetainedUpstreamWebsocketLease:
    effective_max_sessions = _normalize_max_sessions(max_sessions)
    now = time.monotonic()
    normalized_response_id = _normalize_response_id(response_id)

    with _LOCK:
        entry = None
        if normalized_response_id is not None:
            entry = _SESSIONS.get(normalized_response_id)
        if entry is not None:
            if entry.in_use:
                raise ResponsesWebsocketSessionConflictError(
                    f"A stateful HTTP websocket bridge request for response '{normalized_response_id}' is already in progress."
                )
            if _is_upstream_websocket_marked_closed(entry.upstream_ws):
                _close_entry_locked(normalized_response_id)
                entry = None

        if entry is None and normalized_response_id is not None:
            raise ResponsesWebsocketSessionNotFoundError(
                f"No retained upstream websocket exists for response '{normalized_response_id}'."
            )

        if entry is None:
            _evict_to_capacity_locked(effective_max_sessions)
            upstream_ws = create_upstream_websocket()
            _ANONYMOUS_LEASES[id(upstream_ws)] = upstream_ws
            return RetainedUpstreamWebsocketLease(
                response_id=None,
                upstream_ws=upstream_ws,
                created=True,
            )

        entry.in_use = True
        entry.last_used = now
        _SESSIONS.move_to_end(normalized_response_id)
        return RetainedUpstreamWebsocketLease(
            response_id=normalized_response_id,
            upstream_ws=entry.upstream_ws,
            created=False,
        )


def release_retained_upstream_websocket(
    lease: RetainedUpstreamWebsocketLease,
    *,
    retain: bool,
    response_id: str | None = None,
) -> None:
    retained_response_id = _normalize_response_id(response_id) or lease.response_id
    with _LOCK:
        anonymous_upstream = _ANONYMOUS_LEASES.pop(id(lease.upstream_ws), None)
        if anonymous_upstream is not None:
            if retain and retained_response_id and not _is_upstream_websocket_marked_closed(lease.upstream_ws):
                _SESSIONS[retained_response_id] = _RetainedUpstreamWebsocketEntry(
                    upstream_ws=lease.upstream_ws,
                    in_use=False,
                    last_used=time.monotonic(),
                )
                _SESSIONS.move_to_end(retained_response_id)
                return
            _close_upstream_websocket(lease.upstream_ws)
            return

        if lease.response_id is None:
            if not retain:
                _close_upstream_websocket(lease.upstream_ws)
            return

        entry = _SESSIONS.get(lease.response_id)
        if entry is None or entry.upstream_ws is not lease.upstream_ws:
            if not retain:
                _close_upstream_websocket(lease.upstream_ws)
            return

        if retain and retained_response_id and not _is_upstream_websocket_marked_closed(entry.upstream_ws):
            if retained_response_id != lease.response_id:
                _SESSIONS.pop(lease.response_id, None)
                _SESSIONS[retained_response_id] = entry
            entry.in_use = False
            entry.last_used = time.monotonic()
            _SESSIONS.move_to_end(retained_response_id)
            return

        _close_entry_locked(lease.response_id)


def evict_retained_upstream_websocket(response_id: str | None) -> None:
    normalized_response_id = _normalize_response_id(response_id)
    if normalized_response_id is None:
        return
    with _LOCK:
        _close_entry_locked(normalized_response_id)


def reset_retained_upstream_websocket_sessions() -> None:
    with _LOCK:
        for response_id in list(_SESSIONS.keys()):
            _close_entry_locked(response_id)
        for upstream_ws in list(_ANONYMOUS_LEASES.values()):
            _close_upstream_websocket(upstream_ws)
        _ANONYMOUS_LEASES.clear()
