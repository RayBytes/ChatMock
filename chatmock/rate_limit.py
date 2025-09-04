# chatmock/rate_limit.py
from __future__ import annotations

import os
import threading
from collections import deque
from contextlib import contextmanager
from typing import Optional

class GateBusy(Exception):
    """Queue is full; caller should back off."""
    def __init__(self, retry_after_seconds: int = 2):
        super().__init__("Server busy")
        self.retry_after_seconds = int(retry_after_seconds)

class _Permit:
    def __init__(self, gate: "Gate"):
        self._gate = gate
        self._released = False
    def release(self):
        if not self._released:
            self._released = True
            self._gate._release()

class Gate:
    """
    Fair, bounded concurrency gate.
    - max_concurrency: number of simultaneous upstream requests allowed.
    - queue_limit: max number of waiters; beyond this we reject with 429 + Retry-After.
    """
    def __init__(self, max_concurrency: int = 1, queue_limit: int = 100):
        self.max = max(1, int(max_concurrency))
        self.qmax = max(0, int(queue_limit))
        self._lock = threading.Lock()
        self._permits = self.max
        self._waiters = deque()

    def acquire(self, *, wait_timeout: Optional[float] = None) -> _Permit:
        """Acquire a permit or wait fairly. Raise GateBusy if queue is full."""
        ev = None
        with self._lock:
            if self._permits > 0 and not self._waiters:
                self._permits -= 1
                return _Permit(self)
            if len(self._waiters) >= self.qmax:
                raise GateBusy(retry_after_seconds=2)
            ev = threading.Event()
            self._waiters.append(ev)
        signaled = ev.wait(timeout=wait_timeout)
        if not signaled:
            # timed out; withdraw from queue if still present
            with self._lock:
                try:
                    self._waiters.remove(ev)
                except ValueError:
                    pass
            raise GateBusy(retry_after_seconds=2)
        # we were granted a permit
        return _Permit(self)

    def _release(self):
        with self._lock:
            if self._waiters:
                ev = self._waiters.popleft()
                # Do not decrement permits, just hand off directly.
                ev.set()
            else:
                self._permits += 1
                if self._permits > self.max:
                    self._permits = self.max

    @contextmanager
    def acquire_cm(self, *, wait_timeout: Optional[float] = None):
        p = self.acquire(wait_timeout=wait_timeout)
        try:
            yield p
        finally:
            p.release()

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default

# Global gate configured via env
CHATMOCK_MAX_CONCURRENCY = _env_int("CHATMOCK_MAX_CONCURRENCY", 1)
CHATMOCK_QUEUE_LIMIT     = _env_int("CHATMOCK_QUEUE_LIMIT", 100)
CHATMOCK_QUEUE_TIMEOUT_S = _env_int("CHATMOCK_QUEUE_TIMEOUT_S", 60)

gate = Gate(CHATMOCK_MAX_CONCURRENCY, CHATMOCK_QUEUE_LIMIT)
queue_timeout_seconds = CHATMOCK_QUEUE_TIMEOUT_S