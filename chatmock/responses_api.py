from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List

from .fast_mode import ServiceTierResolution, resolve_service_tier
from .model_registry import (
    allowed_efforts_for_model,
    extract_reasoning_from_model_name,
    normalize_model_name,
)
from .reasoning import build_reasoning_param
from .session import ensure_session_id


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
        normalized.pop("instructions", None)

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
    # The Codex backend sends `response.completed` with `output: []` — the items
    # (message, function_call, image_generation_call) only ever arrive in the
    # `response.output_item.done` events. Without rebuilding them here, every
    # non-streaming response comes out empty.
    done_items: Dict[int, Dict[str, Any]] = {}
    fallback_order = 0
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
            if kind == "response.output_item.done":
                item = evt.get("item")
                if isinstance(item, dict):
                    index = evt.get("output_index")
                    if not isinstance(index, int):
                        index = 1_000_000 + fallback_order
                    fallback_order += 1
                    done_items[index] = item
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
    if isinstance(response_obj, dict) and done_items:
        existing = response_obj.get("output")
        if not isinstance(existing, list) or not existing:
            response_obj = dict(response_obj)
            response_obj["output"] = [done_items[key] for key in sorted(done_items)]
    return response_obj, error_obj


def collect_images_from_sse(
    upstream: Any,
) -> tuple[List[Dict[str, Any]], Dict[str, Any] | None, Dict[str, Any] | None, str]:
    """Read the stream to the end and return (image items, usage, error, text).

    Same reason as above: `response.completed` carries no output, so the image
    items only ever exist in the `response.output_item.done` events.

    The text is collected for one reason: when the model finishes without
    drawing, that text is the only place the reason exists. It used to be
    dropped, and the caller was left guessing — the error even said the refusal
    "usually" came from moderation, which nobody had ever confirmed.
    """
    images: List[Dict[str, Any]] = []
    usage: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None
    said: List[str] = []
    try:
        for evt in iter_sse_event_payloads(upstream):
            kind = evt.get("type")
            if kind == "response.output_item.done":
                item = evt.get("item")
                if isinstance(item, dict) and item.get("type") == "image_generation_call":
                    images.append(item)
                elif isinstance(item, dict) and item.get("type") == "message":
                    for part in item.get("content") or []:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            said.append(part["text"])
            elif kind == "response.failed":
                response = evt.get("response")
                if isinstance(response, dict) and isinstance(response.get("error"), dict):
                    error = response["error"]
                else:
                    error = {"message": "response.failed"}
                break
            elif kind == "error":
                error = evt.get("error") if isinstance(evt.get("error"), dict) else {"message": "upstream error"}
                break
            elif kind == "response.completed":
                response = evt.get("response")
                if isinstance(response, dict):
                    tool_usage = response.get("tool_usage")
                    if isinstance(tool_usage, dict) and isinstance(tool_usage.get("image_gen"), dict):
                        usage = tool_usage["image_gen"]
                break
    finally:
        upstream.close()
    return images, usage, error, " ".join(said).strip()


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
