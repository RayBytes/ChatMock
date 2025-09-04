from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request

from .config import BASE_INSTRUCTIONS
from .http import build_cors_headers
from .reasoning import apply_reasoning_to_message, build_reasoning_param, extract_reasoning_from_model_name
from .upstream import normalize_model_name, start_upstream_request
from .utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
    sse_translate_chat,
    sse_translate_text,
)
# ADD:
import os
import random
import time as _time
# Retry/backoff helper that re-invokes start_upstream_request on 429.
def _retry_upstream_call(make_request, *, max_retries: int = 6):
    delay = 0.5
    upstream = None
    error_resp = None
    for attempt in range(max_retries):
        upstream, error_resp = make_request()
        if error_resp is not None:
            return upstream, error_resp
        if upstream is None:
            # Defensive, pass through
            return upstream, error_resp
        if upstream.status_code != 429:
            return upstream, None
        # 429 handling
        ra = upstream.headers.get("retry-after")
        if ra:
            try:
                sleep_for = float(ra)
            except Exception:
                sleep_for = 2.0
        else:
            sleep_for = min(15.0, delay)
            delay *= 2
        sleep_for += random.uniform(0.1, 0.4)
        _time.sleep(sleep_for)
    # Return last 429
    return upstream, None

# Wrap a generator so we can release the gate permit when streaming ends.
def _wrap_stream(gen, on_close):
    try:
        for chunk in gen:
            yield chunk
    finally:
        try:
            on_close()
        except Exception:
            pass
from .rate_limit import gate, GateBusy, queue_timeout_seconds


openai_bp = Blueprint("openai", __name__)


@openai_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")
    debug_model = current_app.config.get("DEBUG_MODEL")

    if verbose:
        try:
            body_preview = (request.get_data(cache=True, as_text=True) or "")[:2000]
            print("IN POST /v1/chat/completions\n" + body_preview)
        except Exception:
            pass

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        try:
            payload = json.loads(raw.replace("\r", "").replace("\n", ""))
        except Exception:
            return jsonify({"error": {"message": "Invalid JSON body"}}), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)
    messages = payload.get("messages")
    if messages is None and isinstance(payload.get("prompt"), str):
        messages = [{"role": "user", "content": payload.get("prompt") or ""}]
    if messages is None and isinstance(payload.get("input"), str):
        messages = [{"role": "user", "content": payload.get("input") or ""}]
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        return jsonify({"error": {"message": "Request must include messages: []"}}), 400

    if isinstance(messages, list):
        sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "system"), None)
        if isinstance(sys_idx, int):
            sys_msg = messages.pop(sys_idx)
            content = sys_msg.get("content") if isinstance(sys_msg, dict) else ""
            messages.insert(0, {"role": "user", "content": content})
    is_stream = bool(payload.get("stream"))
    stream_options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    include_usage = bool(stream_options.get("include_usage", False))

    tools_responses = convert_tools_chat_to_responses(payload.get("tools"))
    tool_choice = payload.get("tool_choice", "auto")
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))

    input_items = convert_chat_messages_to_responses_input(messages)
    if not input_items and isinstance(payload.get("prompt"), str) and payload.get("prompt").strip():
        input_items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": payload.get("prompt")}]}
        ]

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(reasoning_effort, reasoning_summary, reasoning_overrides)

    # Acquire fair gate permit or fail fast with 429 + Retry-After
    try:
        permit = gate.acquire(wait_timeout=queue_timeout_seconds)
    except GateBusy as gb:
        return jsonify({"error": {"message": "Server busy, please retry"}}), 429, {"Retry-After": str(gb.retry_after_seconds)}

    try:
        # Perform upstream call with 429-aware backoff
        def _make():
            return start_upstream_request(
                model,
                input_items,
                instructions=BASE_INSTRUCTIONS,
                tools=tools_responses,
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
            )

        upstream, error_resp = _retry_upstream_call(_make)
        if error_resp is not None:
            # Release permit and return error
            permit.release()
            return error_resp

        created = int(time.time())
        if upstream.status_code >= 400:
            try:
                raw = upstream.content
                err_body = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {"raw": upstream.text}
            except Exception:
                err_body = {"raw": upstream.text}
            if verbose:
                print("Upstream error status=", upstream.status_code, " body:", json.dumps(err_body)[:2000])
            # Bubble up Retry-After if present
            headers = {}
            ra = upstream.headers.get("retry-after")
            if ra:
                headers["Retry-After"] = ra
            # Release permit, since no stream will occur
            permit.release()
            return (
                jsonify({"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}),
                upstream.status_code,
                headers,
            )

        if is_stream:
            resp = Response(
                _wrap_stream(
                    sse_translate_chat(
                        upstream,
                        requested_model or model,
                        created,
                        verbose=verbose,
                        vlog=print if verbose else None,
                        reasoning_compat=reasoning_compat,
                        include_usage=include_usage,
                    ),
                    on_close=permit.release,
                ),
                status=upstream.status_code,
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        # Non-streaming path: keep existing logic, release permit after
        full_text = ""
        reasoning_summary_text = ""
        reasoning_full_text = ""
        response_id = "chatcmpl"
        tool_calls: List[Dict[str, Any]] = []
        error_message: str | None = None
        usage_obj: Dict[str, int] | None = None

        def _extract_usage(evt: Dict[str, Any]) -> Dict[str, int] | None:
            try:
                usage = (evt.get("response") or {}).get("usage")
                if not isinstance(usage, dict):
                    return None
                pt = int(usage.get("input_tokens") or 0)
                ct = int(usage.get("output_tokens") or 0)
                tt = int(usage.get("total_tokens") or (pt + ct))
                return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
            except Exception:
                return None
        try:
            for raw in upstream.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else raw
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    break
                try:
                    evt = json.loads(data)
                except Exception:
                    continue
                kind = evt.get("type")
                mu = _extract_usage(evt)
                if mu:
                    usage_obj = mu
                if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                    response_id = evt["response"].get("id") or response_id
                if kind == "response.output_text.delta":
                    full_text += evt.get("delta") or ""
                elif kind == "response.reasoning_summary_text.delta":
                    reasoning_summary_text += evt.get("delta") or ""
                elif kind == "response.reasoning_text.delta":
                    reasoning_full_text += evt.get("delta") or ""
                elif kind == "response.output_item.done":
                    item = evt.get("item") or {}
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        call_id = item.get("call_id") or item.get("id") or ""
                        name = item.get("name") or ""
                        args = item.get("arguments") or ""
                        if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                            tool_calls.append(
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": name, "arguments": args},
                                }
                            )
                elif kind == "response.failed":
                    error_message = evt.get("response", {}).get("error", {}).get("message", "response.failed")
                elif kind == "response.completed":
                    break
        finally:
            upstream.close()
            permit.release()

        if error_message:
            resp = make_response(jsonify({"error": {"message": error_message}}), 502)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        message: Dict[str, Any] = {"role": "assistant", "content": full_text if full_text else None}
        if tool_calls:
            message["tool_calls"] = tool_calls
        message = apply_reasoning_to_message(message, reasoning_summary_text, reasoning_full_text, reasoning_compat)
        completion = {
            "id": response_id or "chatcmpl",
            "object": "chat.completion",
            "created": created,
            "model": requested_model or model,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "stop",
                }
            ],
            **({"usage": usage_obj} if usage_obj else {}),
        }
        resp = make_response(jsonify(completion), upstream.status_code)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        # Try to forward usage headers if present
        ra = upstream.headers.get("retry-after")
        if ra:
            resp.headers["Retry-After"] = ra
        return resp
    except Exception:
        # Ensure release on unexpected errors
        try:
            permit.release()
        except Exception:
            pass
        raise


@openai_bp.route("/v1/completions", methods=["POST"])
def completions() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    debug_model = current_app.config.get("DEBUG_MODEL")
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return jsonify({"error": {"message": "Invalid JSON body"}}), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)
    prompt = payload.get("prompt")
    if isinstance(prompt, list):
        prompt = "".join([p if isinstance(p, str) else "" for p in prompt])
    if not isinstance(prompt, str):
        prompt = payload.get("suffix") or ""
    stream_req = bool(payload.get("stream", False))
    stream_options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    include_usage = bool(stream_options.get("include_usage", False))

    messages = [{"role": "user", "content": prompt or ""}]
    input_items = convert_chat_messages_to_responses_input(messages)

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(reasoning_effort, reasoning_summary, reasoning_overrides)
    try:
        permit = gate.acquire(wait_timeout=queue_timeout_seconds)
    except GateBusy as gb:
        return jsonify({"error": {"message": "Server busy, please retry"}}), 429, {"Retry-After": str(gb.retry_after_seconds)}

    try:
        def _make():
            return start_upstream_request(
                model,
                input_items,
                instructions=BASE_INSTRUCTIONS,
                reasoning_param=reasoning_param,
            )
        upstream, error_resp = _retry_upstream_call(_make)
        if error_resp is not None:
            permit.release()
            return error_resp

        created = int(time.time())
        if upstream.status_code >= 400:
            try:
                err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"raw": upstream.text}
            except Exception:
                err_body = {"raw": upstream.text}
            headers = {}
            ra = upstream.headers.get("retry-after")
            if ra:
                headers["Retry-After"] = ra
            permit.release()
            return (
                jsonify({"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}),
                upstream.status_code,
                headers,
            )

        if stream_req:
            resp = Response(
                _wrap_stream(
                    sse_translate_text(
                        upstream,
                        requested_model or model,
                        created,
                        verbose=verbose,
                        vlog=(print if verbose else None),
                        include_usage=include_usage,
                    ),
                    on_close=permit.release,
                ),
                status=upstream.status_code,
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        # Non-streaming path: keep existing logic, release permit after
        full_text = ""
        response_id = "cmpl"
        usage_obj: Dict[str, int] | None = None
        def _extract_usage(evt: Dict[str, Any]) -> Dict[str, int] | None:
            try:
                usage = (evt.get("response") or {}).get("usage")
                if not isinstance(usage, dict):
                    return None
                pt = int(usage.get("input_tokens") or 0)
                ct = int(usage.get("output_tokens") or 0)
                tt = int(usage.get("total_tokens") or (pt + ct))
                return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
            except Exception:
                return None
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
                if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                    response_id = evt["response"].get("id") or response_id
                mu = _extract_usage(evt)
                if mu:
                    usage_obj = mu
                kind = evt.get("type")
                if kind == "response.output_text.delta":
                    full_text += evt.get("delta") or ""
                elif kind == "response.completed":
                    break
        finally:
            upstream.close()
            permit.release()

        completion = {
            "id": response_id or "cmpl",
            "object": "text_completion",
            "created": created,
            "model": requested_model or model,
            "choices": [
                {"index": 0, "text": full_text, "finish_reason": "stop", "logprobs": None}
            ],
            **({"usage": usage_obj} if usage_obj else {}),
        }
        resp = make_response(jsonify(completion), upstream.status_code)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        ra = upstream.headers.get("retry-after")
        if ra:
            resp.headers["Retry-After"] = ra
        return resp
    except Exception:
        try:
            permit.release()
        except Exception:
            pass
        raise


@openai_bp.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    data = []
    if expose_variants:
        variant_ids = [
            "gpt-5",
            "gpt-5-high",
            "gpt-5-medium",
            "gpt-5-low",
            "gpt-5-minimal",
        ]
        data = [{"id": mid, "object": "model", "owned_by": "owner"} for mid in variant_ids]
    else:
        data = [{"id": "gpt-5", "object": "model", "owned_by": "owner"}]
    models = {"object": "list", "data": data}
    resp = make_response(jsonify(models), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp
