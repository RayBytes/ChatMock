from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional


# #region agent log
_AGENT_DEBUG_LOG_PATH = r"d:\Dev\chatmock\.cursor\debug.log"


def agent_debug_log(
    *,
    location: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    hypothesisId: str,
    runId: str,
    sessionId: str = "debug-session",
) -> None:
    """Append a single NDJSON line for debug-mode evidence.

    WARNING: Do not log secrets (tokens, api keys, passwords, PII).
    """
    try:
        payload = {
            "id": f"log_{int(time.time() * 1000)}_{int(time.time_ns() % 1_000_000)}",
            "timestamp": int(time.time() * 1000),
            "sessionId": sessionId,
            "runId": runId,
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data or {},
        }
        with open(_AGENT_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Never break the request path for logging.
        pass


# #endregion

