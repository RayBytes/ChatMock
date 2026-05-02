from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS
from .fast_mode import ServiceTierResolution, resolve_service_tier
from .model_registry import (
    allowed_efforts_for_model,
    extract_reasoning_from_model_name,
    normalize_model_name,
    uses_codex_instructions,
)
from .reasoning import build_reasoning_param
from .session import ensure_session_id
from .utils import convert_tools_chat_to_responses


@dataclass(frozen=True)
class ResponsesRequestError(Exception):
    message: str
    status_code: int = 400
    code: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class NormalizedResponsesRequest:
    payload: Dict[str, Any]
    requested_model: str | None
    normalized_model: str
    session_id: str
    service_tier_resolution: ServiceTierResolution


def is_vscode_client_compat(config: Dict[str, Any]) -> bool:
    return str(config.get("CLIENT_COMPAT") or "default").strip().lower() == "vscode"


def _uses_chat_completions_tool_schema(tools: Any) -> bool:
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("function"), dict):
            return True
    return False


def instructions_for_model(config: Dict[str, Any], model: str) -> str:
    base = config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if uses_codex_instructions(model):
        codex = config.get("GPT5_CODEX_INSTRUCTIONS") or GPT5_CODEX_INSTRUCTIONS
        if isinstance(codex, str) and codex.strip():
            return codex
    return base


def extract_client_session_id(headers: Any) -> str | None:
    try:
        return headers.get("X-Session-Id") or headers.get("session_id") or None
    except Exception:
        return None


def _input_items_for_session(raw_input: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_input, list):
        return [item for item in raw_input if isinstance(item, dict)]
    if isinstance(raw_input, dict):
        return [raw_input]
    if isinstance(raw_input, str) and raw_input.strip():
        return [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": raw_input}],
            }
        ]
    return []


def canonicalize_responses_input(raw_input: Any) -> Any:
    if isinstance(raw_input, list):
        return [item for item in raw_input if isinstance(item, dict)]
    if isinstance(raw_input, dict):
        return [raw_input]
    if isinstance(raw_input, str):
        return _input_items_for_session(raw_input)
    return raw_input


def normalize_responses_payload(
    payload: Dict[str, Any],
    *,
    config: Dict[str, Any],
    client_session_id: str | None = None,
) -> NormalizedResponsesRequest:
    if not is_vscode_client_compat(config) and _uses_chat_completions_tool_schema(payload.get("tools")):
        raise ResponsesRequestError(
            "chat.completions tool schema on /v1/responses is only supported when CLIENT_COMPAT=vscode",
            code="CLIENT_COMPAT_UNSUPPORTED",
        )

    requested_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    normalized_model = normalize_model_name(requested_model, config.get("DEBUG_MODEL"))

    normalized = dict(payload)
    normalized["model"] = normalized_model
    normalized.pop("max_output_tokens", None)
    normalized.pop("truncation", None)

    if "input" in normalized:
        normalized["input"] = canonicalize_responses_input(normalized.get("input"))

    normalized["store"] = False

    instructions = normalized.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        instructions = instructions_for_model(config, normalized_model)
        normalized["instructions"] = instructions

    reasoning_effort = config.get("REASONING_EFFORT", "medium")
    reasoning_summary = config.get("REASONING_SUMMARY", "auto")
    reasoning_overrides = (
        normalized.get("reasoning")
        if isinstance(normalized.get("reasoning"), dict)
        else extract_reasoning_from_model_name(requested_model)
    )
    normalized["reasoning"] = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(normalized_model),
    )

    include = normalized.get("include")
    include_list = [item for item in include if isinstance(item, str)] if isinstance(include, list) else []
    if "reasoning.encrypted_content" not in include_list:
        include_list.append("reasoning.encrypted_content")
    normalized["include"] = include_list

    tools = normalized.get("tools")
    converted_tools = convert_tools_chat_to_responses(tools)
    if converted_tools:
        normalized["tools"] = converted_tools
        tools = converted_tools

    if (not isinstance(tools, list) or not tools) and bool(config.get("DEFAULT_WEB_SEARCH")):
        tool_choice = normalized.get("tool_choice")
        if not (isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"):
            normalized["tools"] = [{"type": "web_search"}]

    service_tier_resolution = resolve_service_tier(
        normalized_model,
        request_fast_mode=normalized.get("fast_mode"),
        request_service_tier=normalized.get("service_tier"),
        server_fast_mode=bool(config.get("FAST_MODE")),
    )
    if service_tier_resolution.error_message:
        raise ResponsesRequestError(service_tier_resolution.error_message)
    if service_tier_resolution.service_tier is None:
        normalized.pop("service_tier", None)
    else:
        normalized["service_tier"] = service_tier_resolution.service_tier
    normalized.pop("fast_mode", None)

    input_items = _input_items_for_session(normalized.get("input"))
    session_id = ensure_session_id(instructions, input_items, client_session_id)
    prompt_cache_key = normalized.get("prompt_cache_key")
    if not isinstance(prompt_cache_key, str) or not prompt_cache_key.strip():
        normalized["prompt_cache_key"] = session_id

    return NormalizedResponsesRequest(
        payload=normalized,
        requested_model=requested_model,
        normalized_model=normalized_model,
        session_id=session_id,
        service_tier_resolution=service_tier_resolution,
    )


def iter_sse_event_payloads(upstream: Any) -> Iterator[Dict[str, Any]]:
    for raw in upstream.iter_lines(decode_unicode=False):
        if not raw:
            continue
        line = raw.decode("utf-8", errors="ignore") if isinstance(raw, (bytes, bytearray)) else raw
        if not line.startswith("data: "):
            continue
        data = line[len("data: ") :].strip()
        if not data or data == "[DONE]":
            if data == "[DONE]":
                break
            continue
        try:
            evt = json.loads(data)
        except Exception:
            continue
        if isinstance(evt, dict):
            yield evt


def aggregate_response_from_sse(
    upstream: Any,
    *,
    on_event: Any | None = None,
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    response_obj: Dict[str, Any] | None = None
    error_obj: Dict[str, Any] | None = None
    try:
        for evt in iter_sse_event_payloads(upstream):
            if callable(on_event):
                try:
                    on_event(evt)
                except Exception:
                    pass
            response = evt.get("response")
            if isinstance(response, dict):
                response_obj = response
            kind = evt.get("type")
            if kind == "response.failed":
                if isinstance(response, dict) and isinstance(response.get("error"), dict):
                    error_obj = {"error": response.get("error")}
                else:
                    error_obj = {"error": {"message": "response.failed"}}
                break
            if kind == "response.completed":
                break
    finally:
        upstream.close()
    return response_obj, error_obj


def stream_upstream_bytes(
    upstream: Any,
    *,
    on_event: Any | None = None,
) -> Iterable[bytes]:
    buffer = b""
    try:
        for chunk in upstream.iter_content(chunk_size=None):
            if chunk:
                if callable(on_event):
                    if isinstance(chunk, bytes):
                        buffer += chunk
                    else:
                        buffer += str(chunk).encode("utf-8", errors="ignore")
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line = line.rstrip(b"\r")
                        if not line.startswith(b"data: "):
                            continue
                        data = line[len(b"data: ") :].strip()
                        if not data or data == b"[DONE]":
                            continue
                        try:
                            evt = json.loads(data.decode("utf-8", errors="ignore"))
                        except Exception:
                            evt = None
                        if isinstance(evt, dict):
                            try:
                                on_event(evt)
                            except Exception:
                                pass
                yield chunk
    finally:
        upstream.close()
