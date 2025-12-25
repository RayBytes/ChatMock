from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional


# #region agent log
_PRIMARY_DEBUG_LOG_PATH = Path(r"d:\Dev\chatmock\.cursor\debug.log")
_FALLBACK_DEBUG_LOG_PATH = (Path(__file__).resolve().parents[1] / ".cursor" / "debug.log")
_DEBUG_LOG_CANDIDATES = (_PRIMARY_DEBUG_LOG_PATH, _FALLBACK_DEBUG_LOG_PATH)


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
        wrote = False
        for p in _DEBUG_LOG_CANDIDATES:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                wrote = True
                break
            except Exception:
                continue

        if not wrote:
            # As a last resort, try current working directory `.cursor/debug.log`
            try:
                cwd_path = Path(os.getcwd()) / ".cursor" / "debug.log"
                cwd_path.parent.mkdir(parents=True, exist_ok=True)
                with open(cwd_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
    except Exception:
        # Never break the request path for logging.
        pass


# #endregion

