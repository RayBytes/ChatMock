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


@dataclass(frozen=True)
class RetainedUpstreamWebsocketLease:
    session_id: str
    upstream_ws: Any
    created: bool


@dataclass
class _RetainedUpstreamWebsocketEntry:
    upstream_ws: Any
    in_use: bool
    last_used: float


_SESSIONS: OrderedDict[str, _RetainedUpstreamWebsocketEntry] = OrderedDict()


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


def _close_entry_locked(session_id: str) -> None:
    entry = _SESSIONS.pop(session_id, None)
    if entry is None:
        return
    _close_upstream_websocket(entry.upstream_ws)


def _evict_closed_entries_locked() -> None:
    for session_id, entry in list(_SESSIONS.items()):
        if entry.in_use:
            continue
        if _is_upstream_websocket_marked_closed(entry.upstream_ws):
            _close_entry_locked(session_id)


def _evict_to_capacity_locked(max_sessions: int) -> None:
    _evict_closed_entries_locked()
    while len(_SESSIONS) >= max_sessions:
        evicted = False
        for session_id, entry in list(_SESSIONS.items()):
            if entry.in_use:
                continue
            _close_entry_locked(session_id)
            evicted = True
            break
        if not evicted:
            raise ResponsesWebsocketSessionCapacityError(
                "Too many retained upstream websocket sessions are active right now."
            )


def acquire_retained_upstream_websocket(
    session_id: str,
    create_upstream_websocket: Callable[[], Any],
    *,
    max_sessions: int = DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS,
) -> RetainedUpstreamWebsocketLease:
    effective_max_sessions = _normalize_max_sessions(max_sessions)
    now = time.monotonic()

    with _LOCK:
        entry = _SESSIONS.get(session_id)
        if entry is not None:
            if entry.in_use:
                raise ResponsesWebsocketSessionConflictError(
                    f"A stateful HTTP websocket bridge request for session '{session_id}' is already in progress."
                )
            if _is_upstream_websocket_marked_closed(entry.upstream_ws):
                _close_entry_locked(session_id)
                entry = None

        if entry is None:
            _evict_to_capacity_locked(effective_max_sessions)
            upstream_ws = create_upstream_websocket()
            _SESSIONS[session_id] = _RetainedUpstreamWebsocketEntry(
                upstream_ws=upstream_ws,
                in_use=True,
                last_used=now,
            )
            return RetainedUpstreamWebsocketLease(
                session_id=session_id,
                upstream_ws=upstream_ws,
                created=True,
            )

        entry.in_use = True
        entry.last_used = now
        _SESSIONS.move_to_end(session_id)
        return RetainedUpstreamWebsocketLease(
            session_id=session_id,
            upstream_ws=entry.upstream_ws,
            created=False,
        )


def release_retained_upstream_websocket(
    lease: RetainedUpstreamWebsocketLease,
    *,
    retain: bool,
) -> None:
    with _LOCK:
        entry = _SESSIONS.get(lease.session_id)
        if entry is None or entry.upstream_ws is not lease.upstream_ws:
            if not retain:
                _close_upstream_websocket(lease.upstream_ws)
            return

        if retain and not _is_upstream_websocket_marked_closed(entry.upstream_ws):
            entry.in_use = False
            entry.last_used = time.monotonic()
            _SESSIONS.move_to_end(lease.session_id)
            return

        _close_entry_locked(lease.session_id)


def evict_retained_upstream_websocket(session_id: str) -> None:
    with _LOCK:
        _close_entry_locked(session_id)


def reset_retained_upstream_websocket_sessions() -> None:
    with _LOCK:
        for session_id in list(_SESSIONS.keys()):
            _close_entry_locked(session_id)
