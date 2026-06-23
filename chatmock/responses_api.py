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
from .utils import normalize_tool_choice_for_responses


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


def instructions_for_model(config: Dict[str, Any], model: str) -> str | None:
    if bool(config.get("NO_BASE_INSTRUCTIONS")):
        return None
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
    requested_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    normalized_model = normalize_model_name(requested_model, config.get("DEBUG_MODEL"))

    normalized = dict(payload)
    normalized["model"] = normalized_model
    normalized.pop("max_output_tokens", None)

    if "input" in normalized:
        normalized["input"] = canonicalize_responses_input(normalized.get("input"))

    if "store" not in normalized:
        normalized["store"] = False

    instructions = normalized.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        if not bool(config.get("NO_BASE_INSTRUCTIONS")):
            instructions = instructions_for_model(config, normalized_model)
            normalized["instructions"] = instructions
        else:
            instructions = None

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
    normalized["tool_choice"] = normalize_tool_choice_for_responses(normalized.get("tool_choice", "auto"))

    tools = normalized.get("tools")
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


def compact_response_object(response_obj: Dict[str, Any], model: str | None = None) -> Dict[str, Any]:
    compact = {
        "id": response_obj.get("id"),
        "object": response_obj.get("object") or "response",
        "created_at": response_obj.get("created_at"),
        "status": response_obj.get("status") or "completed",
        "output": response_obj.get("output") if isinstance(response_obj.get("output"), list) else [],
        "model": response_obj.get("model") if isinstance(response_obj.get("model"), str) else model,
    }
    if not isinstance(compact["id"], str) or not compact["id"]:
        compact["id"] = "resp"
    if not isinstance(compact["created_at"], int):
        compact["created_at"] = 0
    return {k: v for k, v in compact.items() if v is not None}


def response_object_from_events(events: List[Dict[str, Any]], model: str | None = None) -> Dict[str, Any] | None:
    response_obj: Dict[str, Any] | None = None
    text_parts: List[str] = []
    done_items: List[tuple[int, Dict[str, Any]]] = []
    for evt in events:
        response = evt.get("response")
        if isinstance(response, dict):
            response_obj = response
        kind = evt.get("type")
        if kind == "response.output_text.delta" and isinstance(evt.get("delta"), str):
            text_parts.append(evt["delta"])
        elif kind == "response.output_item.done" and isinstance(evt.get("item"), dict):
            index = evt.get("output_index")
            done_items.append((index if isinstance(index, int) else len(done_items), evt["item"]))
    if response_obj is None:
        return None
    compact = compact_response_object(response_obj, model)
    if not compact.get("output"):
        if done_items:
            compact["output"] = [item for _, item in sorted(done_items, key=lambda item: item[0])]
        elif text_parts:
            compact["output"] = [
                {
                    "id": f"{compact['id']}_msg",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "".join(text_parts),
                            "annotations": [],
                        }
                    ],
                }
            ]
    return compact


def aggregate_response_from_sse(
    upstream: Any,
    *,
    on_event: Any | None = None,
    model: str | None = None,
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    events: List[Dict[str, Any]] = []
    error_obj: Dict[str, Any] | None = None
    try:
        for evt in iter_sse_event_payloads(upstream):
            events.append(evt)
            if callable(on_event):
                try:
                    on_event(evt)
                except Exception:
                    pass
            response = evt.get("response")
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
    return response_object_from_events(events, model), error_obj


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
