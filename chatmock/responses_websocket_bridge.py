from __future__ import annotations

import json
from typing import Any, Dict

from flask import Response, jsonify, make_response
from websockets.exceptions import ConnectionClosed

from .http import build_cors_headers
from .responses_websocket_sessions import (
    DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS,
    ResponsesWebsocketSessionCapacityError,
    ResponsesWebsocketSessionConflictError,
    RetainedUpstreamWebsocketLease,
    acquire_retained_upstream_websocket,
    evict_retained_upstream_websocket,
    release_retained_upstream_websocket,
)
from .session import (
    clear_responses_reuse_state,
    note_responses_final_response,
    note_responses_stream_event,
)
from .upstream import build_upstream_headers, build_upstream_websocket_url, connect_upstream_websocket
from .utils import get_effective_chatgpt_auth


class ResponsesWebsocketBridgeProtocolError(ValueError):
    pass


def _close_request_upstream_websocket(upstream_ws) -> None:
    try:
        upstream_ws.close()
    except Exception:
        pass


def _log_json(prefix: str, payload: Any) -> None:
    try:
        print(f"{prefix}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        try:
            print(f"{prefix}\n{payload}")
        except Exception:
            pass


def _with_cors(response: Response) -> Response:
    for key, value in build_cors_headers().items():
        response.headers.setdefault(key, value)
    return response


def _json_response(body: Dict[str, Any], *, status_code: int) -> Response:
    return _with_cors(make_response(jsonify(body), status_code))


def _sse_response(payload_iter) -> Response:
    response = Response(
        payload_iter,
        status=200,
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
    return _with_cors(response)


def _terminal_event(event: Dict[str, Any]) -> bool:
    return event.get("type") in ("response.completed", "response.failed", "error")


def parse_upstream_websocket_event(message: Any) -> Dict[str, Any]:
    if isinstance(message, bytes):
        raw_text = message.decode("utf-8", errors="ignore")
    else:
        raw_text = str(message)

    try:
        payload = json.loads(raw_text)
    except Exception as exc:
        raise ResponsesWebsocketBridgeProtocolError(
            "Upstream websocket event payload was not a JSON object"
        ) from exc

    if not isinstance(payload, dict):
        raise ResponsesWebsocketBridgeProtocolError(
            "Upstream websocket event payload was not a JSON object"
        )

    event_type = payload.get("type")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ResponsesWebsocketBridgeProtocolError(
            "Upstream websocket event payload is missing a string type"
        )

    if event_type in ("response.completed", "response.failed") and not isinstance(payload.get("response"), dict):
        raise ResponsesWebsocketBridgeProtocolError(
            f"Upstream websocket {event_type} event is missing a response object"
        )

    return payload


def _recv_upstream_event(upstream_ws) -> Dict[str, Any]:
    try:
        message = upstream_ws.recv()
    except ConnectionClosed as exc:
        raise ResponsesWebsocketBridgeProtocolError(
            "Upstream websocket closed before response.completed"
        ) from exc

    if message is None:
        raise ResponsesWebsocketBridgeProtocolError(
            "Upstream websocket closed before response.completed"
        )

    return parse_upstream_websocket_event(message)


def _encode_sse_event(event: Dict[str, Any]) -> bytes:
    payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    return ("data: " + payload + "\n\n").encode("utf-8")


def _build_upstream_request_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("type") == "response.create":
        return payload
    return {"type": "response.create", **payload}


def _send_upstream_request(upstream_ws, payload: Dict[str, Any], *, verbose: bool) -> None:
    request_event = _build_upstream_request_event(payload)
    if verbose:
        _log_json("OUTBOUND >> ChatGPT Responses WS payload", request_event)
    upstream_ws.send(json.dumps(request_event))


def _release_upstream_websocket(
    upstream_ws,
    *,
    retained_lease: RetainedUpstreamWebsocketLease | None,
    retain: bool,
) -> None:
    if retained_lease is None:
        _close_request_upstream_websocket(upstream_ws)
        return
    release_retained_upstream_websocket(retained_lease, retain=retain)


def _iter_streaming_events(
    upstream_ws,
    *,
    session_id: str,
    verbose: bool,
    retained_lease: RetainedUpstreamWebsocketLease | None = None,
):
    retain_upstream = retained_lease is not None
    released = False
    try:
        while True:
            try:
                event = _recv_upstream_event(upstream_ws)
            except ResponsesWebsocketBridgeProtocolError as exc:
                clear_responses_reuse_state(session_id)
                retain_upstream = False
                error_event = {
                    "type": "error",
                    "status_code": 502,
                    "error": {"message": str(exc)},
                }
                if verbose:
                    _log_json("STREAM OUT /v1/responses (bridge error)", error_event)
                _release_upstream_websocket(
                    upstream_ws,
                    retained_lease=retained_lease,
                    retain=retain_upstream,
                )
                released = True
                yield _encode_sse_event(error_event)
                return

            if verbose:
                _log_json("STREAM OUT /v1/responses (bridge event)", event)
            note_responses_stream_event(session_id, event)
            if event.get("type") in ("response.failed", "error"):
                clear_responses_reuse_state(session_id)
                retain_upstream = False
            if _terminal_event(event):
                _release_upstream_websocket(
                    upstream_ws,
                    retained_lease=retained_lease,
                    retain=retain_upstream,
                )
                released = True
            yield _encode_sse_event(event)
            if _terminal_event(event):
                return
    finally:
        if not released:
            _release_upstream_websocket(
                upstream_ws,
                retained_lease=retained_lease,
                retain=retain_upstream,
            )


def _collect_response(
    upstream_ws,
    *,
    session_id: str,
    verbose: bool,
    retained_lease: RetainedUpstreamWebsocketLease | None = None,
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None, int]:
    response_obj: Dict[str, Any] | None = None
    retain_upstream = retained_lease is not None
    try:
        while True:
            event = _recv_upstream_event(upstream_ws)
            if verbose:
                _log_json("STREAM OUT /v1/responses (bridge event)", event)

            event_type = event.get("type")
            if event_type != "response.completed":
                note_responses_stream_event(session_id, event)

            response = event.get("response")
            if isinstance(response, dict):
                response_obj = response

            if event_type == "response.failed":
                clear_responses_reuse_state(session_id)
                retain_upstream = False
                error = response.get("error") if isinstance(response.get("error"), dict) else {"message": "response.failed"}
                return None, {"error": error}, 502
            if event_type == "error":
                clear_responses_reuse_state(session_id)
                retain_upstream = False
                error = event.get("error") if isinstance(event.get("error"), dict) else {"message": "Upstream websocket error"}
                status_code = event.get("status_code") if isinstance(event.get("status_code"), int) else 502
                return None, {"error": error}, status_code
            if event_type == "response.completed":
                return response_obj, None, 200
    except ResponsesWebsocketBridgeProtocolError as exc:
        clear_responses_reuse_state(session_id)
        retain_upstream = False
        return None, {"error": {"message": str(exc)}}, 502
    finally:
        _release_upstream_websocket(
            upstream_ws,
            retained_lease=retained_lease,
            retain=retain_upstream,
        )


def send_responses_request_via_websocket(
    *,
    payload: Dict[str, Any],
    session_id: str,
    stream: bool,
    verbose: bool = False,
    stateful: bool = False,
    explicit_previous_response_id: bool = False,
    max_retained_sessions: int = DEFAULT_MAX_RETAINED_UPSTREAM_WEBSOCKETS,
) -> Response:
    # HTTP bridge mode is transport-only: one HTTP request owns one upstream
    # websocket connection, while session.py remains the only reuse-state owner.
    if stateful and explicit_previous_response_id:
        evict_retained_upstream_websocket(session_id)

    access_token, account_id = get_effective_chatgpt_auth()
    if not access_token or not account_id:
        if stateful:
            evict_retained_upstream_websocket(session_id)
        clear_responses_reuse_state(session_id)
        return _json_response(
            {
                "error": {
                    "message": "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first.",
                }
            },
            status_code=401,
        )

    def _connect_upstream_websocket():
        return connect_upstream_websocket(
            build_upstream_websocket_url(),
            build_upstream_headers(
                access_token,
                account_id,
                session_id,
                accept="application/json",
            ),
        )

    retained_lease: RetainedUpstreamWebsocketLease | None = None
    try:
        if stateful:
            retained_lease = acquire_retained_upstream_websocket(
                session_id,
                _connect_upstream_websocket,
                max_sessions=max_retained_sessions,
            )
            upstream_ws = retained_lease.upstream_ws
        else:
            upstream_ws = _connect_upstream_websocket()
    except ResponsesWebsocketSessionConflictError as exc:
        return _json_response(
            {"error": {"message": str(exc)}},
            status_code=409,
        )
    except ResponsesWebsocketSessionCapacityError as exc:
        clear_responses_reuse_state(session_id)
        return _json_response(
            {"error": {"message": str(exc)}},
            status_code=503,
        )
    except Exception as exc:
        clear_responses_reuse_state(session_id)
        if stateful:
            evict_retained_upstream_websocket(session_id)
        return _json_response(
            {"error": {"message": f"Upstream websocket connection failed: {exc}"}},
            status_code=502,
        )

    try:
        _send_upstream_request(upstream_ws, payload, verbose=verbose)
    except Exception as exc:
        clear_responses_reuse_state(session_id)
        _release_upstream_websocket(
            upstream_ws,
            retained_lease=retained_lease,
            retain=False,
        )
        return _json_response(
            {"error": {"message": f"Upstream websocket request send failed: {exc}"}},
            status_code=502,
        )

    if stream:
        stream_iter = _iter_streaming_events(
            upstream_ws,
            session_id=session_id,
            verbose=verbose,
            retained_lease=retained_lease,
        )
        if retained_lease is not None:
            return _sse_response(list(stream_iter))
        return _sse_response(stream_iter)

    response_obj, error_obj, status_code = _collect_response(
        upstream_ws,
        session_id=session_id,
        verbose=verbose,
        retained_lease=retained_lease,
    )
    if error_obj is not None:
        return _json_response(error_obj, status_code=status_code)
    if response_obj is None:
        clear_responses_reuse_state(session_id)
        return _json_response(
            {"error": {"message": "Upstream websocket closed before response.completed"}},
            status_code=502,
        )
    note_responses_final_response(session_id, response_obj)
    return _json_response(response_obj, status_code=status_code)