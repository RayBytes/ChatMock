"""OpenAI-compatible API routes backed by ChatGPT Responses."""

from __future__ import annotations

import json
import time
from http import HTTPStatus
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, make_response, request

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS
from .http import build_cors_headers
from .limits import record_rate_limits_from_response
from .reasoning import (
    apply_reasoning_to_message,
    build_reasoning_param,
    extract_reasoning_from_model_name,
)
from .upstream import normalize_model_name, start_upstream_request
from .utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
    sse_translate_chat,
    sse_translate_text,
)

openai_bp = Blueprint("openai", __name__)


def _instructions_for_model(model: str) -> str:
    base = current_app.config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if model == "gpt-5-codex":
        codex = current_app.config.get("GPT5_CODEX_INSTRUCTIONS") or GPT5_CODEX_INSTRUCTIONS
        if isinstance(codex, str) and codex.strip():
            return codex
    return base


@openai_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:  # noqa: C901, PLR0911, PLR0912, PLR0915
    """Translate Chat Completions into Responses API and stream back."""
    verbose = bool(current_app.config.get("VERBOSE"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")
    debug_model = current_app.config.get("DEBUG_MODEL")

    if verbose:
        body_preview = (request.get_data(cache=True, as_text=True) or "")[:2000]
        current_app.logger.info("IN POST /v1/chat/completions\n%s", body_preview)

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        try:
            payload = json.loads(raw.replace("\r", "").replace("\n", ""))
        except json.JSONDecodeError:
            return jsonify({"error": {"message": "Invalid JSON body"}}), HTTPStatus.BAD_REQUEST

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

    # messages is guaranteed to be a list above; normalize a preceding system message
    sys_idx = next(
        (i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "system"),
        None,
    )
    if isinstance(sys_idx, int):
        sys_msg = messages.pop(sys_idx)
        content = sys_msg.get("content") if isinstance(sys_msg, dict) else ""
        messages.insert(0, {"role": "user", "content": content})
    is_stream = bool(payload.get("stream"))
    stream_options = (
        payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    )
    include_usage = bool(stream_options.get("include_usage", False))

    tools_responses = convert_tools_chat_to_responses(payload.get("tools"))
    tool_choice = payload.get("tool_choice", "auto")
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))
    responses_tools_payload = (
        payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    )
    extra_tools: list[dict[str, Any]] = []
    had_responses_tools = False
    if isinstance(responses_tools_payload, list):
        for _t in responses_tools_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            if _t.get("type") not in ("web_search", "web_search_preview"):
                return (
                    jsonify(
                        {
                            "error": {
                                "message": (
                                    "Only web_search/web_search_preview are supported in "
                                    "responses_tools"
                                ),
                                "code": "RESPONSES_TOOL_UNSUPPORTED",
                            }
                        }
                    ),
                    HTTPStatus.BAD_REQUEST,
                )
            extra_tools.append(_t)

        if not extra_tools and bool(current_app.config.get("DEFAULT_WEB_SEARCH")):
            responses_tool_choice = payload.get("responses_tool_choice")
            if not (isinstance(responses_tool_choice, str) and responses_tool_choice == "none"):
                extra_tools = [{"type": "web_search"}]

        if extra_tools:
            max_tools_bytes = 32768
            try:
                size = len(json.dumps(extra_tools))
            except (TypeError, ValueError):
                size = 0
            if size > max_tools_bytes:
                return jsonify(
                    {
                        "error": {
                            "message": "responses_tools too large",
                            "code": "RESPONSES_TOOLS_TOO_LARGE",
                        }
                    }
                ), HTTPStatus.BAD_REQUEST
            had_responses_tools = True
            tools_responses = (tools_responses or []) + extra_tools

    responses_tool_choice = payload.get("responses_tool_choice")
    if isinstance(responses_tool_choice, str) and responses_tool_choice in ("auto", "none"):
        tool_choice = responses_tool_choice

    input_items = convert_chat_messages_to_responses_input(messages)
    if not input_items and isinstance(payload.get("prompt"), str) and payload.get("prompt").strip():
        input_items = [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": payload.get("prompt")}],
            }
        ]

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = (
        payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    )
    reasoning_param = build_reasoning_param(
        reasoning_effort, reasoning_summary, reasoning_overrides
    )

    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=_instructions_for_model(model),
        tools=tools_responses,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        reasoning_param=reasoning_param,
    )
    if error_resp is not None:
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= HTTPStatus.BAD_REQUEST:
        try:
            raw = upstream.content
            err_body = (
                json.loads(raw.decode("utf-8", errors="ignore")) if raw else {"raw": upstream.text}
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            err_body = {"raw": upstream.text}
        if had_responses_tools:
            if verbose:
                current_app.logger.info(
                    "[Passthrough] Upstream rejected tools; retrying without extra tools "
                    "(args redacted)"
                )
            base_tools_only = convert_tools_chat_to_responses(payload.get("tools"))
            safe_choice = payload.get("tool_choice", "auto")
            upstream2, err2 = start_upstream_request(
                model,
                input_items,
                instructions=BASE_INSTRUCTIONS,
                tools=base_tools_only,
                tool_choice=safe_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
            )
            record_rate_limits_from_response(upstream2)
            if (
                err2 is None
                and upstream2 is not None
                and upstream2.status_code < HTTPStatus.BAD_REQUEST
            ):
                upstream = upstream2
            else:
                return (
                    jsonify(
                        {
                            "error": {
                                "message": (err_body.get("error", {}) or {}).get(
                                    "message", "Upstream error"
                                ),
                                "code": "RESPONSES_TOOLS_REJECTED",
                            }
                        }
                    ),
                    (upstream2.status_code if upstream2 is not None else upstream.status_code),
                )
        else:
            if verbose:
                current_app.logger.info("Upstream error status=%s", upstream.status_code)
            return (
                jsonify(
                    {
                        "error": {
                            "message": (err_body.get("error", {}) or {}).get(
                                "message", "Upstream error"
                            )
                        }
                    }
                ),
                upstream.status_code,
            )

    if is_stream:
        resp = Response(
            sse_translate_chat(
                upstream,
                requested_model or model,
                created,
                verbose=verbose,
                vlog=(current_app.logger.info if verbose else None),
                reasoning_compat=reasoning_compat,
                include_usage=include_usage,
            ),
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
    tool_calls: list[dict[str, Any]] = []
    error_message: str | None = None
    usage_obj: dict[str, int] | None = None

    def _extract_usage(evt: dict[str, Any]) -> dict[str, int] | None:
        try:
            usage = (evt.get("response") or {}).get("usage")
            if not isinstance(usage, dict):
                return None
            pt = int(usage.get("input_tokens") or 0)
            ct = int(usage.get("output_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
        except (TypeError, ValueError, AttributeError, KeyError):
            return None
        else:
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}

    try:
        for raw in upstream.iter_lines(decode_unicode=False):
            if not raw:
                continue
            line = (
                raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else raw
            )
            if not line.startswith("data: "):
                continue
            data = line[len("data: ") :].strip()
            if not data:
                continue
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
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
                error_message = (
                    evt.get("response", {}).get("error", {}).get("message", "response.failed")
                )
            elif kind == "response.completed":
                break
    finally:
        upstream.close()

    if error_message:
        resp = make_response(jsonify({"error": {"message": error_message}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    message: dict[str, Any] = {"role": "assistant", "content": full_text if full_text else None}
    if tool_calls:
        message["tool_calls"] = tool_calls
    message = apply_reasoning_to_message(
        message, reasoning_summary_text, reasoning_full_text, reasoning_compat
    )
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
    return resp


@openai_bp.route("/v1/completions", methods=["POST"])
def completions() -> Response:  # noqa: C901, PLR0912, PLR0915
    """Translate Text Completions into Responses API and stream back."""
    verbose = bool(current_app.config.get("VERBOSE"))
    debug_model = current_app.config.get("DEBUG_MODEL")
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return jsonify({"error": {"message": "Invalid JSON body"}}), HTTPStatus.BAD_REQUEST

    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)
    prompt = payload.get("prompt")
    if isinstance(prompt, list):
        prompt = "".join([p if isinstance(p, str) else "" for p in prompt])
    if not isinstance(prompt, str):
        prompt = payload.get("suffix") or ""
    stream_req = bool(payload.get("stream", False))
    stream_options = (
        payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    )
    include_usage = bool(stream_options.get("include_usage", False))

    messages = [{"role": "user", "content": prompt or ""}]
    input_items = convert_chat_messages_to_responses_input(messages)

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = (
        payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    )
    reasoning_param = build_reasoning_param(
        reasoning_effort, reasoning_summary, reasoning_overrides
    )
    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=_instructions_for_model(model),
        reasoning_param=reasoning_param,
    )
    if error_resp is not None:
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= HTTPStatus.BAD_REQUEST:
        try:
            err_body = (
                json.loads(upstream.content.decode("utf-8", errors="ignore"))
                if upstream.content
                else {"raw": upstream.text}
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            err_body = {"raw": upstream.text}
        return (
            jsonify(
                {
                    "error": {
                        "message": (err_body.get("error", {}) or {}).get(
                            "message", "Upstream error"
                        )
                    }
                }
            ),
            upstream.status_code,
        )

    if stream_req:
        resp = Response(
            sse_translate_text(
                upstream,
                requested_model or model,
                created,
                verbose=verbose,
                vlog=(current_app.logger.info if verbose else None),
                include_usage=include_usage,
            ),
            status=upstream.status_code,
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    full_text = ""
    response_id = "cmpl"
    usage_obj: dict[str, int] | None = None

    def _extract_usage(evt: dict[str, Any]) -> dict[str, int] | None:
        try:
            usage = (evt.get("response") or {}).get("usage")
            if not isinstance(usage, dict):
                return None
            pt = int(usage.get("input_tokens") or 0)
            ct = int(usage.get("output_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
        except (TypeError, ValueError, AttributeError, KeyError):
            return None
        else:
            return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}

    try:
        for raw_line in upstream.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            line = (
                raw_line.decode("utf-8", errors="ignore")
                if isinstance(raw_line, (bytes, bytearray))
                else raw_line
            )
            if not line.startswith("data: "):
                continue
            data = line[len("data: ") :].strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    break
                continue
            try:
                evt = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
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
        "choices": [{"index": 0, "text": full_text, "finish_reason": "stop", "logprobs": None}],
        **({"usage": usage_obj} if usage_obj else {}),
    }
    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    """Return a synthetic list of models compatible with OpenAI clients."""
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    model_groups = [
        ("gpt-5", ["high", "medium", "low", "minimal"]),
        ("gpt-5-codex", ["high", "medium", "low"]),
        ("codex-mini", []),
    ]
    model_ids: list[str] = []
    for base, efforts in model_groups:
        model_ids.append(base)
        if expose_variants:
            model_ids.extend([f"{base}-{effort}" for effort in efforts])
    data = [{"id": mid, "object": "model", "owned_by": "owner"} for mid in model_ids]
    models = {"object": "list", "data": data}
    resp = make_response(jsonify(models), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp
