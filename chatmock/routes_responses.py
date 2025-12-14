"""Experimental Responses API endpoint.

This module provides a Responses-compatible API surface at /v1/responses.
It proxies to ChatGPT's internal backend-api/codex/responses endpoint.

Key constraints of the ChatGPT upstream:
- store=false is REQUIRED (upstream rejects store=true with 400 error)
- previous_response_id is NOT supported upstream
- stream=true is required for upstream

We implement local polyfills for store and previous_response_id to provide
a more complete API experience.
"""
from __future__ import annotations

import json
import time
import threading
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, current_app, jsonify, make_response, request, stream_with_context
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout

try:
    from urllib3.exceptions import ProtocolError
except Exception:
    ProtocolError = Exception  # type: ignore

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS
from .http import build_cors_headers
from .limits import record_rate_limits_from_response
from .reasoning import build_reasoning_param, extract_reasoning_from_model_name
from .upstream import normalize_model_name, start_upstream_request
from .utils import convert_chat_messages_to_responses_input, convert_tools_chat_to_responses

try:
    from .routes_webui import record_request
except ImportError:
    record_request = None  # type: ignore

responses_bp = Blueprint("responses", __name__)

# Simple in-memory store for Response objects (FIFO, size-limited)
_STORE_LOCK = threading.Lock()
_STORE: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_MAX_STORE_ITEMS = 200

# Simple in-memory threads map: response_id -> list of input items
# representing the conversation so far for previous_response_id simulation
_THREADS_LOCK = threading.Lock()
_THREADS: Dict[str, List[Dict[str, Any]]] = {}
_MAX_THREAD_ITEMS = 40


def _store_response(obj: Dict[str, Any]) -> None:
    """Store a response object in memory for later retrieval."""
    try:
        rid = obj.get("id")
        if not isinstance(rid, str) or not rid:
            return
        with _STORE_LOCK:
            if rid in _STORE:
                _STORE.pop(rid, None)
            _STORE[rid] = obj
            while len(_STORE) > _MAX_STORE_ITEMS:
                _STORE.popitem(last=False)
    except Exception:
        pass


def _get_response(rid: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored response by ID."""
    with _STORE_LOCK:
        return _STORE.get(rid)


def _set_thread(rid: str, items: List[Dict[str, Any]]) -> None:
    """Store conversation thread for previous_response_id simulation."""
    try:
        if not (isinstance(rid, str) and rid and isinstance(items, list)):
            return
        trimmed = items[-_MAX_THREAD_ITEMS:]
        with _THREADS_LOCK:
            _THREADS[rid] = trimmed
    except Exception:
        pass


def _get_thread(rid: str) -> Optional[List[Dict[str, Any]]]:
    """Get conversation thread for a response ID."""
    with _THREADS_LOCK:
        return _THREADS.get(rid)


def _collect_rs_ids(obj: Any, parent_key: Optional[str] = None, out: Optional[List[str]] = None) -> List[str]:
    """Collect strings that look like upstream response ids (rs_*) in structural fields."""
    if out is None:
        out = []
    try:
        if isinstance(obj, str):
            key = (parent_key or "").lower()
            structural_keys = {"previous_response_id", "response_id", "reference_id", "item_id"}
            if key in structural_keys and obj.strip().startswith("rs_"):
                out.append(obj.strip())
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _collect_rs_ids(v, k, out)
        elif isinstance(obj, list):
            for v in obj:
                _collect_rs_ids(v, parent_key, out)
    except Exception:
        pass
    return out


def _sanitize_input_remove_refs(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove upstream rs_* references from input items."""
    def drop_ref_fields(d: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("previous_response_id", "response_id", "reference_id", "item_id"):
            if isinstance(d.get(key), str) and d.get(key, "").startswith("rs_"):
                d.pop(key, None)
        return d

    out: List[Dict[str, Any]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        it2 = drop_ref_fields(dict(it))
        content = it2.get("content")
        if isinstance(content, list):
            new_parts = []
            for p in content:
                if not isinstance(p, dict):
                    new_parts.append(p)
                    continue
                if _collect_rs_ids(p):
                    p = {k: v for k, v in p.items()
                         if k not in ("previous_response_id", "response_id", "reference_id", "item_id")}
                new_parts.append(p)
            it2["content"] = new_parts
        out.append(it2)
    return out


def _instructions_for_model(model: str) -> str:
    """Get base instructions for a model."""
    base = current_app.config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if model == "gpt-5-codex":
        codex = current_app.config.get("GPT5_CODEX_INSTRUCTIONS") or GPT5_CODEX_INSTRUCTIONS
        if isinstance(codex, str) and codex.strip():
            return codex
    return base


def _generate_response_id() -> str:
    """Generate a unique response ID."""
    return f"resp_{uuid.uuid4().hex[:24]}"


def _extract_usage(evt: Dict[str, Any]) -> Optional[Dict[str, int]]:
    """Extract usage info from an event."""
    try:
        usage = (evt.get("response") or {}).get("usage")
        if not isinstance(usage, dict):
            return None
        pt = int(usage.get("input_tokens") or 0)
        ct = int(usage.get("output_tokens") or 0)
        tt = int(usage.get("total_tokens") or (pt + ct))
        return {"input_tokens": pt, "output_tokens": ct, "total_tokens": tt}
    except Exception:
        return None


@responses_bp.route("/v1/responses", methods=["POST"])
def responses_create() -> Response:
    """Create a Response (streaming or non-streaming).

    This endpoint provides a Responses-compatible API that proxies to
    ChatGPT's internal responses endpoint with local polyfills for
    store and previous_response_id.
    """
    request_start = time.time()
    verbose = bool(current_app.config.get("VERBOSE"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    debug_model = current_app.config.get("DEBUG_MODEL")

    # Parse request body
    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return jsonify({"error": {"message": "Invalid JSON body"}}), 400

    # Determine streaming mode (default: true)
    stream_req = payload.get("stream")
    if stream_req is None:
        stream_req = True
    stream_req = bool(stream_req)

    # Get and normalize model
    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)

    debug = bool(current_app.config.get("DEBUG_LOG"))
    if debug:
        print(f"[responses] {requested_model} -> {model}")

    # Parse input - accept Responses `input` or Chat-style `messages`/`prompt`
    input_items: Optional[List[Dict[str, Any]]] = None
    raw_input = payload.get("input")

    if isinstance(raw_input, list):
        # Check if it's a list of content parts (like input_text) vs list of message items
        if raw_input and all(isinstance(x, dict) and x.get("type") in ("input_text", "input_image", "output_text") for x in raw_input):
            # Looks like content parts, wrap in a user message (no "type": "message" - just role + content)
            input_items = [{"role": "user", "content": raw_input}]
        else:
            # Already structured input - pass through but strip "type": "message" if present
            input_items = []
            for x in raw_input:
                if not isinstance(x, dict):
                    continue
                item = dict(x)
                # Remove "type": "message" - upstream doesn't accept it
                if item.get("type") == "message":
                    item.pop("type", None)
                input_items.append(item)
    elif isinstance(raw_input, str):
        # Simple string input - wrap in user message with input_text
        input_items = [{"role": "user", "content": [{"type": "input_text", "text": raw_input}]}]
    elif isinstance(raw_input, dict):
        item = dict(raw_input)
        # Remove "type": "message" if present
        if item.get("type") == "message":
            item.pop("type", None)
        if isinstance(item.get("role"), str) and isinstance(item.get("content"), list):
            input_items = [item]
        elif isinstance(item.get("content"), list):
            input_items = [{"role": "user", "content": item.get("content") or []}]

    # Sanitize input to remove upstream rs_* references
    if isinstance(raw_input, list):
        try:
            raw_input = _sanitize_input_remove_refs(raw_input)
        except Exception:
            pass

    # Fallback to messages/prompt
    if input_items is None:
        messages = payload.get("messages")
        if messages is None and isinstance(payload.get("prompt"), str):
            messages = [{"role": "user", "content": payload.get("prompt") or ""}]
        if isinstance(messages, list):
            input_items = convert_chat_messages_to_responses_input(messages)

    if not isinstance(input_items, list) or not input_items:
        return jsonify({"error": {"message": "Request must include non-empty 'input' (or 'messages'/'prompt')"}}), 400

    # Final sanitization
    input_items = _sanitize_input_remove_refs(input_items)

    # Handle previous_response_id (local threading simulation)
    prev_id = payload.get("previous_response_id")
    if isinstance(prev_id, str) and prev_id.strip():
        prior = _get_thread(prev_id.strip())
        if isinstance(prior, list) and prior:
            input_items = prior + input_items

    # Parse tools
    tools_responses: List[Dict[str, Any]] = []
    _tools = payload.get("tools")
    if isinstance(_tools, list):
        for t in _tools:
            if not isinstance(t, dict):
                continue
            if t.get("type") == "function" and isinstance(t.get("function"), dict):
                tools_responses.extend(convert_tools_chat_to_responses([t]))
            elif isinstance(t.get("type"), str):
                tools_responses.append(t)

    tool_choice = payload.get("tool_choice", "auto")
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))

    # Handle responses_tools (web_search passthrough)
    rt_payload = payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    if isinstance(rt_payload, list):
        for _t in rt_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            if _t.get("type") not in ("web_search", "web_search_preview"):
                return jsonify({"error": {"message": "Only web_search/web_search_preview supported in responses_tools"}}), 400
            tools_responses.append(_t)

    # Default web search if enabled and no tools specified
    if not rt_payload and bool(current_app.config.get("DEFAULT_WEB_SEARCH")):
        rtc = payload.get("responses_tool_choice")
        if not (isinstance(rtc, str) and rtc == "none"):
            tools_responses.append({"type": "web_search"})

    rtc = payload.get("responses_tool_choice")
    if isinstance(rtc, str) and rtc in ("auto", "none"):
        tool_choice = rtc

    # Handle instructions
    no_base = bool(current_app.config.get("RESPONSES_NO_BASE_INSTRUCTIONS"))
    base_inst = _instructions_for_model(model)
    user_inst = payload.get("instructions") if isinstance(payload.get("instructions"), str) else None

    if no_base:
        instructions = user_inst.strip() if isinstance(user_inst, str) and user_inst.strip() else "You are a helpful assistant."
    else:
        instructions = base_inst
        if isinstance(user_inst, str) and user_inst.strip():
            lead_item = {"role": "user", "content": [{"type": "input_text", "text": user_inst}]}
            input_items = [lead_item] + (input_items or [])

    # Build reasoning param
    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(reasoning_effort, reasoning_summary, reasoning_overrides)

    # Passthrough fields (NOT store or previous_response_id - those are local only)
    passthrough_keys = ["temperature", "top_p", "seed", "stop", "text", "metadata", "include", "top_logprobs", "truncation"]
    extra_fields: Dict[str, Any] = {}
    for k in passthrough_keys:
        if k in payload and payload.get(k) is not None:
            extra_fields[k] = payload.get(k)

    # Store flag for local use (not forwarded upstream)
    store_locally = bool(payload.get("store", False))

    # Make upstream request
    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=instructions,
        tools=tools_responses,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        reasoning_param=reasoning_param,
        extra_fields=extra_fields,
    )
    if error_resp is not None:
        return error_resp

    record_rate_limits_from_response(upstream)

    if upstream.status_code >= 400:
        try:
            err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"raw": upstream.text}
        except Exception:
            err_body = {"raw": upstream.text}
        error_msg = (err_body.get("error", {}) or {}).get("message", "Upstream error")
        return jsonify({"error": {"message": error_msg}}), upstream.status_code

    if stream_req:
        # Streaming mode - passthrough SSE events
        def _passthrough():
            try:
                for chunk in upstream.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    yield chunk
            except (ChunkedEncodingError, ProtocolError, ConnectionError, ReadTimeout):
                return
            except Exception:
                return
            finally:
                try:
                    upstream.close()
                except Exception:
                    pass
                # Record streaming request (without token counts)
                if record_request is not None:
                    try:
                        record_request(
                            model=model,
                            endpoint="/v1/responses",
                            success=True,
                            response_time=time.time() - request_start,
                            total_tokens=0,
                            prompt_tokens=0,
                            completion_tokens=0,
                        )
                    except Exception:
                        pass

        resp = Response(
            stream_with_context(_passthrough()),
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    # Non-streaming mode - aggregate response
    created = int(time.time())
    response_id = _generate_response_id()
    usage_obj: Optional[Dict[str, int]] = None
    full_text = ""
    output_items: List[Dict[str, Any]] = []
    upstream_response_id: Optional[str] = None

    try:
        for raw_line in upstream.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="ignore") if isinstance(raw_line, (bytes, bytearray)) else raw_line
            if not line.startswith("data: "):
                continue
            data = line[len("data: "):].strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    break
                continue
            try:
                evt = json.loads(data)
            except Exception:
                continue

            kind = evt.get("type")

            # Capture response ID from upstream
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                upstream_response_id = evt["response"].get("id")

            if kind == "response.output_text.delta":
                delta = evt.get("delta") or ""
                full_text += delta
            elif kind == "response.output_item.done":
                item = evt.get("item")
                if isinstance(item, dict):
                    output_items.append(item)
            elif kind == "response.completed":
                usage_obj = _extract_usage(evt)
                # Also capture any final output from response.completed
                resp_obj = evt.get("response")
                if isinstance(resp_obj, dict):
                    output = resp_obj.get("output")
                    if isinstance(output, list) and not output_items:
                        output_items = output
    except Exception:
        pass
    finally:
        try:
            upstream.close()
        except Exception:
            pass

    # Build output items if we only have text
    if not output_items and full_text:
        output_items = [{
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": full_text}]
        }]

    # Build response object
    response_obj: Dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "created_at": created,
        "model": model,
        "output": output_items,
        "status": "completed",
    }
    if usage_obj:
        response_obj["usage"] = usage_obj

    # Store if requested
    if store_locally:
        _store_response(response_obj)
        # Also store thread for previous_response_id simulation
        thread_items = list(input_items)
        for item in output_items:
            if isinstance(item, dict):
                thread_items.append(item)
        _set_thread(response_id, thread_items)

    # Record request in statistics
    if record_request is not None:
        try:
            record_request(
                model=model,
                endpoint="/v1/responses",
                success=True,
                response_time=time.time() - request_start,
                total_tokens=usage_obj.get("total_tokens", 0) if usage_obj else 0,
                prompt_tokens=usage_obj.get("input_tokens", 0) if usage_obj else 0,
                completion_tokens=usage_obj.get("output_tokens", 0) if usage_obj else 0,
            )
        except Exception:
            pass

    resp = make_response(jsonify(response_obj), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@responses_bp.route("/v1/responses/<response_id>", methods=["GET"])
def responses_retrieve(response_id: str) -> Response:
    """Retrieve a stored response by ID.

    Only works for responses created with store=true (local storage only,
    as upstream ChatGPT endpoint doesn't support store=true).
    """
    stored = _get_response(response_id)
    if stored is None:
        resp = make_response(
            jsonify({"error": {"message": f"Response '{response_id}' not found", "code": "not_found"}}),
            404
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    resp = make_response(jsonify(stored), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@responses_bp.route("/v1/responses", methods=["OPTIONS"])
@responses_bp.route("/v1/responses/<response_id>", methods=["OPTIONS"])
def responses_options(**kwargs) -> Response:
    """Handle CORS preflight requests."""
    resp = make_response("", 204)
    for k, v in build_cors_headers().items():
        resp.headers[k] = v
    return resp
