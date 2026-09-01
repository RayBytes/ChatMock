from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request

from .fast_mode import resolve_service_tier
from .images_api import (
    DEFAULT_IMAGE_ORCHESTRATOR_MODEL,
    IMAGE_TOOL_TYPE,
    MAX_IMAGES_PER_REQUEST,
    build_image_request_payload,
    image_item_to_openai,
    image_markdown_for_item,
    usage_to_openai,
)
from .limits import record_rate_limits_from_response
from .http import build_cors_headers
from .model_registry import list_public_models
from .responses_api import (
    ResponsesRequestError,
    aggregate_response_from_sse,
    collect_images_from_sse,
    extract_client_session_id,
    normalize_responses_payload,
    stream_upstream_bytes,
)
from .reasoning import (
    allowed_efforts_for_model,
    apply_reasoning_to_message,
    build_reasoning_param,
    extract_reasoning_from_model_name,
)
from .session import (
    clear_responses_reuse_state,
    note_responses_final_response,
    note_responses_stream_event,
    prepare_responses_request_for_session,
)
from .upstream import normalize_model_name, start_upstream_raw_request, start_upstream_request
from .utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
    sse_translate_chat,
    sse_translate_text,
)


openai_bp = Blueprint("openai", __name__)


def _log_json(prefix: str, payload: Any) -> None:
    try:
        print(f"{prefix}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        try:
            print(f"{prefix}\n{payload}")
        except Exception:
            pass


def _wrap_stream_logging(label: str, iterator, enabled: bool):
    if not enabled:
        return iterator

    def _gen():
        for chunk in iterator:
            try:
                text = (
                    chunk.decode("utf-8", errors="replace")
                    if isinstance(chunk, (bytes, bytearray))
                    else str(chunk)
                )
                print(f"{label}\n{text}")
            except Exception:
                pass
            yield chunk

    return _gen()


def _service_tier_from_payload(
    model: str,
    payload: Dict[str, Any],
    *,
    verbose: bool = False,
) -> tuple[str | None, Response | None]:
    resolution = resolve_service_tier(
        model,
        request_fast_mode=payload.get("fast_mode"),
        request_service_tier=payload.get("service_tier"),
        server_fast_mode=bool(current_app.config.get("FAST_MODE")),
    )
    if resolution.warning_message and verbose:
        print(f"[FastMode] {resolution.warning_message}")
    if resolution.error_message:
        err = {"error": {"message": resolution.error_message}}
        if verbose:
            _log_json("OUT POST service_tier resolution", err)
        resp = make_response(jsonify(err), 400)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp
    return resolution.service_tier, None


@openai_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")

    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            print("IN POST /v1/chat/completions\n" + raw)
        except Exception:
            pass
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        try:
            payload = json.loads(raw.replace("\r", "").replace("\n", ""))
        except Exception:
            err = {"error": {"message": "Invalid JSON body"}}
            if verbose:
                _log_json("OUT POST /v1/chat/completions", err)
            return jsonify(err), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, current_app.config.get("DEBUG_MODEL"))
    messages = payload.get("messages")
    if messages is None and isinstance(payload.get("prompt"), str):
        messages = [{"role": "user", "content": payload.get("prompt") or ""}]
    if messages is None and isinstance(payload.get("input"), str):
        messages = [{"role": "user", "content": payload.get("input") or ""}]
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        err = {"error": {"message": "Request must include messages: []"}}
        if verbose:
            _log_json("OUT POST /v1/chat/completions", err)
        return jsonify(err), 400

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
    responses_tools_payload = payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    extra_tools: List[Dict[str, Any]] = []
    had_responses_tools = False
    if isinstance(responses_tools_payload, list):
        for _t in responses_tools_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            if _t.get("type") not in ("web_search", "web_search_preview", IMAGE_TOOL_TYPE):
                err = {
                    "error": {
                        "message": (
                            "Only web_search/web_search_preview/image_generation are supported "
                            "in responses_tools"
                        ),
                        "code": "RESPONSES_TOOL_UNSUPPORTED",
                    }
                }
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                return jsonify(err), 400
            extra_tools.append(_t)

        if not extra_tools and bool(current_app.config.get("DEFAULT_WEB_SEARCH")):
            responses_tool_choice = payload.get("responses_tool_choice")
            if not (isinstance(responses_tool_choice, str) and responses_tool_choice == "none"):
                extra_tools = [{"type": "web_search"}]

        if extra_tools:
            import json as _json
            MAX_TOOLS_BYTES = 32768
            try:
                size = len(_json.dumps(extra_tools))
            except Exception:
                size = 0
            if size > MAX_TOOLS_BYTES:
                err = {"error": {"message": "responses_tools too large", "code": "RESPONSES_TOOLS_TOO_LARGE"}}
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                return jsonify(err), 400
            had_responses_tools = True
            tools_responses = (tools_responses or []) + extra_tools

    responses_tool_choice = payload.get("responses_tool_choice")
    if isinstance(responses_tool_choice, str) and responses_tool_choice in ("auto", "none"):
        tool_choice = responses_tool_choice

    input_items = convert_chat_messages_to_responses_input(messages)
    if not input_items and isinstance(payload.get("prompt"), str) and payload.get("prompt").strip():
        input_items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": payload.get("prompt")}]}
        ]

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )
    service_tier, tier_error = _service_tier_from_payload(model, payload, verbose=verbose)
    if tier_error is not None:
        return tier_error

    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        tools=tools_responses,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        reasoning_param=reasoning_param,
        service_tier=service_tier,
    )
    if error_resp is not None:
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/chat/completions", parsed)
            except Exception:
                pass
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= 400:
        try:
            raw = upstream.content
            err_body = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {"raw": upstream.text}
        except Exception:
            err_body = {"raw": upstream.text}
        if had_responses_tools:
            if verbose:
                print("[Passthrough] Upstream rejected tools; retrying without extra tools (args redacted)")
            base_tools_only = convert_tools_chat_to_responses(payload.get("tools"))
            safe_choice = payload.get("tool_choice", "auto")
            upstream2, err2 = start_upstream_request(
                model,
                input_items,
                tools=base_tools_only,
                tool_choice=safe_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
                service_tier=service_tier,
            )
            record_rate_limits_from_response(upstream2)
            if err2 is None and upstream2 is not None and upstream2.status_code < 400:
                upstream = upstream2
            else:
                err = {
                    "error": {
                        "message": (err_body.get("error", {}) or {}).get("message", "Upstream error"),
                        "code": "RESPONSES_TOOLS_REJECTED",
                    }
                }
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                return jsonify(err), (upstream2.status_code if upstream2 is not None else upstream.status_code)
        else:
            if verbose:
                print("Upstream error status=", upstream.status_code)
            err = {"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}
            if verbose:
                _log_json("OUT POST /v1/chat/completions", err)
            return jsonify(err), upstream.status_code

    if is_stream:
        if verbose:
            print("OUT POST /v1/chat/completions (streaming response)")
        stream_iter = sse_translate_chat(
            upstream,
            requested_model or model,
            created,
            verbose=verbose_obfuscation,
            vlog=print if verbose_obfuscation else None,
            reasoning_compat=reasoning_compat,
            include_usage=include_usage,
        )
        stream_iter = _wrap_stream_logging("STREAM OUT /v1/chat/completions", stream_iter, verbose)
        resp = Response(
            stream_iter,
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

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
                if isinstance(item, dict) and item.get("type") == "image_generation_call":
                    full_text += image_markdown_for_item(item)
                elif isinstance(item, dict) and item.get("type") == "function_call":
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
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        **({"usage": usage_obj} if usage_obj else {}),
    }
    if verbose:
        _log_json("OUT POST /v1/chat/completions", completion)
    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/completions", methods=["POST"])
def completions() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")

    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            print("IN POST /v1/completions\n" + raw)
        except Exception:
            pass
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        err = {"error": {"message": "Invalid JSON body"}}
        if verbose:
            _log_json("OUT POST /v1/completions", err)
        return jsonify(err), 400

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, current_app.config.get("DEBUG_MODEL"))
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
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )
    service_tier, tier_error = _service_tier_from_payload(model, payload, verbose=verbose)
    if tier_error is not None:
        return tier_error
    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        reasoning_param=reasoning_param,
        service_tier=service_tier,
    )
    if error_resp is not None:
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/completions", parsed)
            except Exception:
                pass
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= 400:
        try:
            err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"raw": upstream.text}
        except Exception:
            err_body = {"raw": upstream.text}
        err = {"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}
        if verbose:
            _log_json("OUT POST /v1/completions", err)
        return jsonify(err), upstream.status_code

    if stream_req:
        if verbose:
            print("OUT POST /v1/completions (streaming response)")
        stream_iter = sse_translate_text(
            upstream,
            requested_model or model,
            created,
            verbose=verbose_obfuscation,
            vlog=(print if verbose_obfuscation else None),
            include_usage=include_usage,
        )
        stream_iter = _wrap_stream_logging("STREAM OUT /v1/completions", stream_iter, verbose)
        resp = Response(
            stream_iter,
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

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
    if verbose:
        _log_json("OUT POST /v1/completions", completion)
    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/responses", methods=["POST"])
def responses_create() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            print("IN POST /v1/responses\n" + raw)
        except Exception:
            pass

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        err = {"error": {"message": "Invalid JSON body"}}
        if verbose:
            _log_json("OUT POST /v1/responses", err)
        return jsonify(err), 400

    if not isinstance(payload, dict):
        err = {"error": {"message": "Request body must be a JSON object"}}
        if verbose:
            _log_json("OUT POST /v1/responses", err)
        return jsonify(err), 400

    try:
        normalized = normalize_responses_payload(
            payload,
            config=current_app.config,
            client_session_id=extract_client_session_id(request.headers),
        )
    except ResponsesRequestError as exc:
        err: Dict[str, Any] = {"error": {"message": str(exc)}}
        if exc.code:
            err["error"]["code"] = exc.code
        if verbose:
            _log_json("OUT POST /v1/responses", err)
        return jsonify(err), exc.status_code

    if normalized.service_tier_resolution.warning_message and verbose:
        print(f"[FastMode] {normalized.service_tier_resolution.warning_message}")

    prepared = prepare_responses_request_for_session(
        normalized.session_id,
        normalized.payload,
        allow_previous_response_id=False,
    )
    stream_req = bool(prepared.payload.get("stream", False))
    upstream_payload = dict(prepared.payload)
    upstream_payload["stream"] = True
    upstream, error_resp = start_upstream_raw_request(
        upstream_payload,
        session_id=normalized.session_id,
        stream=True,
    )
    if error_resp is not None:
        clear_responses_reuse_state(normalized.session_id)
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/responses", parsed)
            except Exception:
                pass
        return error_resp

    record_rate_limits_from_response(upstream)

    if upstream.status_code >= 400:
        try:
            err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"error": {"message": upstream.text}}
        except Exception:
            err_body = {"error": {"message": upstream.text or "Upstream error"}}
        finally:
            upstream.close()
        clear_responses_reuse_state(normalized.session_id)
        if verbose:
            _log_json("OUT POST /v1/responses", err_body)
        resp = make_response(jsonify(err_body), upstream.status_code)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    if stream_req:
        if verbose:
            print("OUT POST /v1/responses (streaming response)")
        stream_iter = _wrap_stream_logging(
            "STREAM OUT /v1/responses",
            stream_upstream_bytes(
                upstream,
                on_event=lambda evt: note_responses_stream_event(normalized.session_id, evt),
            ),
            verbose,
        )
        resp = Response(
            stream_iter,
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    content_type = upstream.headers.get("Content-Type", "")
    if "application/json" in content_type.lower():
        try:
            body = upstream.json()
        except Exception:
            body = None
        finally:
            upstream.close()
        if isinstance(body, dict):
            note_responses_final_response(normalized.session_id, body)
            if verbose:
                _log_json("OUT POST /v1/responses", body)
            resp = make_response(jsonify(body), upstream.status_code)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

    response_obj, error_obj = aggregate_response_from_sse(
        upstream,
        on_event=lambda evt: note_responses_stream_event(normalized.session_id, evt),
    )
    if error_obj is not None:
        clear_responses_reuse_state(normalized.session_id)
        if verbose:
            _log_json("OUT POST /v1/responses", error_obj)
        resp = make_response(jsonify(error_obj), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    if response_obj is None:
        clear_responses_reuse_state(normalized.session_id)
        err = {"error": {"message": "Upstream response stream did not contain a completed response object"}}
        if verbose:
            _log_json("OUT POST /v1/responses", err)
        resp = make_response(jsonify(err), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    if verbose:
        _log_json("OUT POST /v1/responses", response_obj)
    resp = make_response(jsonify(response_obj), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


def _images_error(message: str, status: int, code: str | None = None) -> Response:
    body: Dict[str, Any] = {"error": {"message": message}}
    if code:
        body["error"]["code"] = code
    resp = make_response(jsonify(body), status)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


def _run_image_request(
    upstream_payload: Dict[str, Any],
    *,
    session_id: str | None,
    verbose: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any] | None, Response | None, str]:
    upstream, error_resp = start_upstream_raw_request(
        upstream_payload,
        session_id=session_id,
        stream=True,
    )
    if error_resp is not None:
        return [], None, error_resp, ""

    record_rate_limits_from_response(upstream)

    if upstream.status_code >= 400:
        try:
            raw = upstream.content
            err_body = json.loads(raw.decode("utf-8", errors="ignore")) if raw else {}
        except Exception:
            err_body = {}
        finally:
            upstream.close()

        err_info = err_body.get("error") if isinstance(err_body.get("error"), dict) else {}
        param = err_info.get("param") if isinstance(err_info.get("param"), str) else ""
        tools = upstream_payload.get("tools")
        tool = tools[0] if isinstance(tools, list) and tools and isinstance(tools[0], dict) else {}
        # The backend refuses image parameters it does not know (that is what
        # happens with 'n'). Rather than forwarding the 400, retry once with a
        # bare tool: the caller gets the image, just without the tweak it asked
        # for.
        if err_info.get("code") == "unknown_parameter" and param.startswith("tools[") and len(tool) > 1:
            if verbose:
                print(f"[Images] Backend rejected '{param}'; retrying without the tool parameters")
            retry_payload = dict(upstream_payload)
            retry_payload["tools"] = [{"type": IMAGE_TOOL_TYPE}]
            return _run_image_request(retry_payload, session_id=session_id, verbose=verbose)

        message = err_info.get("message") or "Upstream error"
        return [], None, _images_error(str(message), upstream.status_code), ""

    images, usage, error, said = collect_images_from_sse(upstream)
    if error is not None:
        message = error.get("message") if isinstance(error, dict) else None
        return [], None, _images_error(str(message or "Upstream error"), 502), said
    return images, usage, None, said


@openai_bp.route("/v1/images/generations", methods=["POST"])
def images_generations() -> Response:
    verbose = bool(current_app.config.get("VERBOSE"))
    raw = request.get_data(cache=True, as_text=True) or ""
    if verbose:
        try:
            # Truncated on purpose: an 'image' reference arrives here as a data
            # URL and would otherwise dump megabytes into the log.
            print("IN POST /v1/images/generations\n" + raw[:2000])
        except Exception:
            pass

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return _images_error("Invalid JSON body", 400)
    if not isinstance(payload, dict):
        return _images_error("Request body must be a JSON object", 400)

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return _images_error("Missing required parameter: 'prompt'", 400)

    response_format = payload.get("response_format")
    if isinstance(response_format, str) and response_format.strip().lower() == "url":
        return _images_error(
            "response_format 'url' is not available: the backend returns base64 and ChatMock "
            "hosts no files. Use 'b64_json'.",
            400,
            code="unsupported_value",
        )

    try:
        n = int(payload.get("n") or 1)
    except (TypeError, ValueError):
        return _images_error("Parameter 'n' must be an integer", 400)
    if n < 1:
        return _images_error("Parameter 'n' must be >= 1", 400)
    if n > MAX_IMAGES_PER_REQUEST:
        return _images_error(
            f"Parameter 'n' must be <= {MAX_IMAGES_PER_REQUEST}: the backend draws one image per "
            "call, so every extra unit is another request against your quota.",
            400,
        )

    input_images = payload.get("image")
    if isinstance(input_images, str):
        input_images = [input_images]
    elif not isinstance(input_images, list):
        input_images = []

    orchestrator = payload.get("chat_model")
    if not isinstance(orchestrator, str) or not orchestrator.strip():
        orchestrator = current_app.config.get("IMAGE_ORCHESTRATOR_MODEL") or DEFAULT_IMAGE_ORCHESTRATOR_MODEL
    orchestrator = normalize_model_name(orchestrator, current_app.config.get("DEBUG_MODEL"))

    upstream_payload = build_image_request_payload(
        prompt.strip(),
        model=orchestrator,
        tool_params=payload,
        input_images=[img for img in input_images if isinstance(img, str)],
    )

    session_id = extract_client_session_id(request.headers)
    collected: List[Dict[str, Any]] = []
    usage_totals: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    saw_usage = False
    # Kept across rounds: with n > 1 the last round is the one that explains an
    # empty result, and each round overwrites the previous.
    last_text = ""
    for _ in range(n):
        images, usage, error_resp, said = _run_image_request(
            upstream_payload,
            session_id=session_id,
            verbose=verbose,
        )
        if error_resp is not None:
            return error_resp
        if said:
            last_text = said
        collected.extend(images)
        normalized_usage = usage_to_openai(usage)
        if normalized_usage:
            saw_usage = True
            for key in usage_totals:
                usage_totals[key] += int(normalized_usage.get(key) or 0)

    if not collected:
        # Say what the model said, instead of guessing why it stopped. This
        # error used to assert the prompt "usually" hit moderation, which was
        # never verified: the text that carries the actual reason was being
        # thrown away one function up.
        spoken = last_text.strip()
        if spoken:
            detail = f' The model answered instead of drawing: "{spoken[:400]}"'
        else:
            detail = (
                " It returned no text either, so the request was most likely stopped before the "
                "model started working."
            )
        return _images_error(
            "The model finished without generating an image." + detail,
            502,
            code="no_image_returned",
        )

    body: Dict[str, Any] = {
        "created": int(time.time()),
        "data": [image_item_to_openai(item) for item in collected],
    }
    if saw_usage:
        body["usage"] = usage_totals
    if verbose:
        # Not _log_json: a single image is a couple of megabytes of base64, and
        # printing the body would drown the log.
        print(f"OUT POST /v1/images/generations ({len(collected)} image(s))")

    resp = make_response(jsonify(body), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    model_ids = list_public_models(expose_reasoning_models=expose_variants)
    data = [{"id": mid, "object": "model", "owned_by": "owner"} for mid in model_ids]
    models = {"object": "list", "data": data}
    resp = make_response(jsonify(models), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp
