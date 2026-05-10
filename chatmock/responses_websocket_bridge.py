from __future__ import annotations

from typing import Any, Dict

from flask import Response


def send_responses_request_via_websocket(
    *,
    payload: Dict[str, Any],
    session_id: str,
    stream: bool,
    verbose: bool = False,
) -> Response:
    raise NotImplementedError("WebSocket upstream bridge is not implemented yet.")