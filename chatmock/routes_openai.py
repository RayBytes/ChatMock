from __future__ import annotations

import json
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request
import os

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
    # Passthrough Responses API tools from Chat Completions (web_search only)
    responses_tools_payload = payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    extra_tools: List[Dict[str, Any]] = []
    had_responses_tools = False
    if isinstance(responses_tools_payload, list):
        for _t in responses_tools_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            # Restrict passthrough strictly to the built-in web_search tool.
            if _t.get("type") != "web_search":
                return (
                    jsonify(
                        {
                            "error": {
                                "message": "Only web_search is supported in responses_tools",
                                "code": "RESPONSES_TOOL_UNSUPPORTED",
                            }
                        }
                    ),
                    400,
                )
            extra_tools.append(_t)

        if extra_tools:
            import json as _json

            max_bytes = int(os.getenv("RESPONSES_TOOLS_MAX_BYTES", "32768") or "32768")
            try:
                size = len(_json.dumps(extra_tools))
            except Exception:
                size = 0
            if size > max_bytes:
                return jsonify({"error": {"message": "responses_tools too large", "code": "RESPONSES_TOOLS_TOO_LARGE"}}), 400
            had_responses_tools = True
            tools_responses = (tools_responses or []) + extra_tools

    # Only allow string tool_choice values (auto|none) from passthrough
    responses_tool_choice = payload.get("responses_tool_choice")
    if isinstance(responses_tool_choice, str) and responses_tool_choice in ("auto", "none"):
        tool_choice = responses_tool_choice

