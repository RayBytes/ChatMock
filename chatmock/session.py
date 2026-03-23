from __future__ import annotations

import copy
import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


_LOCK = threading.Lock()
_FINGERPRINT_TO_UUID: Dict[str, str] = {}
_ORDER: List[str] = []
_MAX_ENTRIES = 10000
_RESPONSES_SESSION_STATE: Dict[str, "_ResponsesSessionState"] = {}
_RESPONSES_ORDER: List[str] = []


@dataclass(frozen=True)
class PreparedResponsesRequest:
    payload: Dict[str, Any]
    session_id: str


@dataclass
class _ResponsesSessionState:
    last_request_payload: Dict[str, Any] | None = None
    last_response_id: str | None = None
    last_response_items: List[Dict[str, Any]] = field(default_factory=list)
    inflight_request_payload: Dict[str, Any] | None = None
    inflight_track_result: bool = False
    inflight_response_id: str | None = None
    inflight_response_items: List[Dict[str, Any]] = field(default_factory=list)


def _canonicalize_first_user_message(input_items: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """
    Extract the first stable user message from Responses input items. Good use for a fingerprint for prompt caching.
    """
    for item in input_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        role = item.get("role")
        if role != "user":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        norm_content = []
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "input_text":
                text = part.get("text") if isinstance(part.get("text"), str) else ""
                if text:
                    norm_content.append({"type": "input_text", "text": text})
            elif ptype == "input_image":
                url = part.get("image_url") if isinstance(part.get("image_url"), str) else None
                if url:
                    norm_content.append({"type": "input_image", "image_url": url})
        if norm_content:
            return {"type": "message", "role": "user", "content": norm_content}
    return None


def canonicalize_prefix(instructions: str | None, input_items: List[Dict[str, Any]]) -> str:
    prefix: Dict[str, Any] = {}
    if isinstance(instructions, str) and instructions.strip():
        prefix["instructions"] = instructions.strip()
    first_user = _canonicalize_first_user_message(input_items)
    if first_user is not None:
        prefix["first_user_message"] = first_user
    return json.dumps(prefix, sort_keys=True, separators=(",", ":"))


def _fingerprint(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _remember(fp: str, sid: str) -> None:
    if fp in _FINGERPRINT_TO_UUID:
        return
    _FINGERPRINT_TO_UUID[fp] = sid
    _ORDER.append(fp)
    if len(_ORDER) > _MAX_ENTRIES:
        oldest = _ORDER.pop(0)
        _FINGERPRINT_TO_UUID.pop(oldest, None)


def _remember_responses_session(session_id: str) -> _ResponsesSessionState:
    state = _RESPONSES_SESSION_STATE.get(session_id)
    if state is None:
        state = _ResponsesSessionState()
        _RESPONSES_SESSION_STATE[session_id] = state
        _RESPONSES_ORDER.append(session_id)
        if len(_RESPONSES_ORDER) > _MAX_ENTRIES:
            oldest = _RESPONSES_ORDER.pop(0)
            _RESPONSES_SESSION_STATE.pop(oldest, None)
    return state


def _request_without_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    clone = copy.deepcopy(payload)
    clone["input"] = []
    clone.pop("previous_response_id", None)
    return clone


def _input_list(payload: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    raw = payload.get("input")
    if not isinstance(raw, list):
        return None
    return [item for item in copy.deepcopy(raw) if isinstance(item, dict)]


def _conversation_output_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reusable: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "reasoning":
            continue
        reusable.append(copy.deepcopy(item))
    return reusable


def _clear_reuse_state(state: _ResponsesSessionState) -> None:
    state.last_request_payload = None
    state.last_response_id = None
    state.last_response_items = []
    state.inflight_request_payload = None
    state.inflight_track_result = False
    state.inflight_response_id = None
    state.inflight_response_items = []


def _clear_inflight(state: _ResponsesSessionState) -> None:
    state.inflight_request_payload = None
    state.inflight_track_result = False
    state.inflight_response_id = None
    state.inflight_response_items = []


def ensure_session_id(
    instructions: str | None,
    input_items: List[Dict[str, Any]],
    client_supplied: str | None = None,
) -> str:
    if isinstance(client_supplied, str) and client_supplied.strip():
        return client_supplied.strip()

    canon = canonicalize_prefix(instructions, input_items)
    fp = _fingerprint(canon)
    with _LOCK:
        if fp in _FINGERPRINT_TO_UUID:
            return _FINGERPRINT_TO_UUID[fp]
        sid = str(uuid.uuid4())
        _remember(fp, sid)
        return sid


def prepare_responses_request_for_session(
    session_id: str,
    payload: Dict[str, Any],
    *,
    allow_previous_response_id: bool = True,
) -> PreparedResponsesRequest:
    full_payload = copy.deepcopy(payload)
    outbound_payload = copy.deepcopy(payload)
    explicit_previous_response_id = (
        isinstance(full_payload.get("previous_response_id"), str)
        and bool(full_payload.get("previous_response_id").strip())
    )

    with _LOCK:
        state = _remember_responses_session(session_id)

        if explicit_previous_response_id:
            _clear_reuse_state(state)
            return PreparedResponsesRequest(
                payload=outbound_payload,
                session_id=session_id,
            )

        request_input = _input_list(full_payload)
        if (
            allow_previous_response_id
            and
            state.last_request_payload is not None
            and state.last_response_id
            and request_input is not None
            and _request_without_input(state.last_request_payload) == _request_without_input(full_payload)
        ):
            baseline: List[Dict[str, Any]] = []
            previous_input = _input_list(state.last_request_payload)
            if previous_input is not None:
                baseline.extend(previous_input)
            baseline.extend(copy.deepcopy(state.last_response_items))
            baseline_len = len(baseline)
            if request_input[:baseline_len] == baseline and baseline_len <= len(request_input):
                outbound_payload["input"] = copy.deepcopy(request_input[baseline_len:])
                outbound_payload["previous_response_id"] = state.last_response_id

        state.inflight_request_payload = full_payload
        state.inflight_track_result = True
        state.inflight_response_id = None
        state.inflight_response_items = []

    return PreparedResponsesRequest(
        payload=outbound_payload,
        session_id=session_id,
    )


def note_responses_stream_event(session_id: str, event: Dict[str, Any]) -> None:
    if not isinstance(session_id, str) or not session_id.strip():
        return
    if not isinstance(event, dict):
        return

    with _LOCK:
        state = _RESPONSES_SESSION_STATE.get(session_id)
        if state is None:
            return

        kind = event.get("type")
        if kind == "response.created":
            response = event.get("response")
            if isinstance(response, dict) and isinstance(response.get("id"), str):
                state.inflight_response_id = response.get("id")
            return

        if kind == "response.output_item.done":
            item = event.get("item")
            if isinstance(item, dict):
                state.inflight_response_items.append(copy.deepcopy(item))
            return

        if kind == "response.completed":
            response = event.get("response")
            response_id = None
            response_items: List[Dict[str, Any]] = copy.deepcopy(state.inflight_response_items)
            if isinstance(response, dict):
                if isinstance(response.get("id"), str):
                    response_id = response.get("id")
                output = response.get("output")
                if isinstance(output, list) and output:
                    response_items = [copy.deepcopy(item) for item in output if isinstance(item, dict)]
            if not response_id:
                response_id = state.inflight_response_id

            if state.inflight_track_result and state.inflight_request_payload is not None and response_id:
                state.last_request_payload = copy.deepcopy(state.inflight_request_payload)
                state.last_response_id = response_id
                state.last_response_items = _conversation_output_items(response_items)
            else:
                state.last_request_payload = None
                state.last_response_id = None
                state.last_response_items = []
            _clear_inflight(state)
            return

        if kind in ("response.failed", "error"):
            _clear_reuse_state(state)


def note_responses_final_response(session_id: str, response_obj: Dict[str, Any]) -> None:
    if not isinstance(session_id, str) or not session_id.strip():
        return
    if not isinstance(response_obj, dict):
        return

    with _LOCK:
        state = _RESPONSES_SESSION_STATE.get(session_id)
        if state is None:
            return

        response_id = response_obj.get("id") if isinstance(response_obj.get("id"), str) else None
        output = response_obj.get("output")
        output_items = [copy.deepcopy(item) for item in output if isinstance(item, dict)] if isinstance(output, list) else []
        if state.inflight_track_result and state.inflight_request_payload is not None and response_id:
            state.last_request_payload = copy.deepcopy(state.inflight_request_payload)
            state.last_response_id = response_id
            state.last_response_items = _conversation_output_items(output_items)
        else:
            state.last_request_payload = None
            state.last_response_id = None
            state.last_response_items = []
        _clear_inflight(state)


def clear_responses_reuse_state(session_id: str) -> None:
    if not isinstance(session_id, str) or not session_id.strip():
        return
    with _LOCK:
        state = _RESPONSES_SESSION_STATE.get(session_id)
        if state is None:
            return
        _clear_reuse_state(state)


def reset_session_state() -> None:
    with _LOCK:
        _FINGERPRINT_TO_UUID.clear()
        _ORDER.clear()
        _RESPONSES_SESSION_STATE.clear()
        _RESPONSES_ORDER.clear()
