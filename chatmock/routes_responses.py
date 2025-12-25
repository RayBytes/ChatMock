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

import atexit
import json
import os
import time
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, current_app, jsonify, make_response, request, stream_with_context
from requests.exceptions import ChunkedEncodingError, ConnectionError, ReadTimeout

try:
    from urllib3.exceptions import ProtocolError
except ImportError:
    ProtocolError = Exception  # type: ignore

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS, has_official_instructions
from .debug import dump_request, dump_tools_debug
from .http import build_cors_headers
from .limits import record_rate_limits_from_response
from .reasoning import build_reasoning_param, extract_reasoning_from_model_name
from .upstream import normalize_model_name, start_upstream_request
from .utils import convert_chat_messages_to_responses_input, convert_tools_chat_to_responses, get_home_dir

try:
    from .routes_webui import record_request
except ImportError:
    record_request = None  # type: ignore

responses_bp = Blueprint("responses", __name__)

# Tool name length limit (ChatGPT API requirement)
_TOOL_NAME_LIMIT = 64


def _shorten_tool_name(name: str) -> str:
    """Shorten tool name to fit within 64 character limit.

    MCP tools often have long names like 'mcp__server-name__tool_name'.
    We preserve the mcp__ prefix and last segment when possible.
    """
    if len(name) <= _TOOL_NAME_LIMIT:
        return name

    # For MCP tools, try to keep prefix and last segment
    if name.startswith("mcp__"):
        # Find last __ separator
        idx = name.rfind("__")
        if idx > 4:  # More than just "mcp__"
            candidate = "mcp__" + name[idx + 2:]
            if len(candidate) <= _TOOL_NAME_LIMIT:
                return candidate

    # Fallback: truncate
    return name[:_TOOL_NAME_LIMIT]


def _build_tool_name_map(tools: List[Dict[str, Any]]) -> Dict[str, str]:
    """Build a map of original tool names to shortened unique names.

    Ensures uniqueness by adding ~1, ~2 suffixes if needed.
    """
    if not tools:
        return {}

    # Collect original names
    names = []
    for t in tools:
        name = None
        if t.get("type") == "function":
            fn = t.get("function") or t
            name = fn.get("name")
        elif "name" in t:
            name = t.get("name")
        if name:
            names.append(name)

    if not names:
        return {}

    # Build shortened names with uniqueness
    used: set = set()
    result: Dict[str, str] = {}

    for original in names:
        short = _shorten_tool_name(original)

        # If shortened name conflicts, add suffix
        if short in used:
            suffix = 1
            while f"{short[:_TOOL_NAME_LIMIT - 3]}~{suffix}" in used:
                suffix += 1
            short = f"{short[:_TOOL_NAME_LIMIT - 3]}~{suffix}"

        used.add(short)
        if short != original:
            result[original] = short

    return result


def _apply_tool_name_shortening(tools: List[Dict[str, Any]], name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Apply tool name shortening to a list of tools."""
    if not name_map:
        return tools

    result = []
    for t in tools:
        t = dict(t)  # shallow copy

        if t.get("type") == "function" and isinstance(t.get("function"), dict):
            fn = dict(t["function"])
            name = fn.get("name")
            if name and name in name_map:
                fn["name"] = name_map[name]
                t["function"] = fn
        elif "name" in t:
            name = t.get("name")
            if name and name in name_map:
                t["name"] = name_map[name]

        result.append(t)

    return result


def _apply_tool_name_shortening_to_input(items: List[Dict[str, Any]], name_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Apply tool name shortening to function_call items in input.

    function_call items have a 'name' field that references the tool.
    """
    if not name_map:
        return items

    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(item)
            continue

        item_type = item.get("type")

        # function_call items have 'name' field
        if item_type == "function_call":
            name = item.get("name")
            if name and name in name_map:
                item = dict(item)
                item["name"] = name_map[name]

        result.append(item)

    return result

# Simple in-memory store for Response objects (FIFO, size-limited)
_STORE_LOCK = threading.Lock()
_STORE: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_MAX_STORE_ITEMS = 200

# Simple in-memory threads map: response_id -> list of input items (FIFO, size-limited)
# representing the conversation so far for previous_response_id simulation
_THREADS_LOCK = threading.Lock()
_THREADS: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
_MAX_THREAD_ITEMS = 40
_MAX_THREAD_RESPONSES = 200

# Persistence file names
_STORE_FILE = "responses_store.json"
_THREADS_FILE = "responses_threads.json"
_PERSISTENCE_ENABLED = True  # Can be disabled via env var


def _get_persistence_dir() -> Path:
    """Get directory for persistence files."""
    return Path(get_home_dir())


def _load_persisted_data() -> None:
    """Load persisted store and threads from disk on startup."""
    global _STORE, _THREADS
    if not _PERSISTENCE_ENABLED:
        return

    persist_dir = _get_persistence_dir()

    # Load store
    store_path = persist_dir / _STORE_FILE
    if store_path.exists():
        try:
            with open(store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                with _STORE_LOCK:
                    _STORE.clear()
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, dict):
                            _STORE[k] = v
                    # Trim to max size
                    while len(_STORE) > _MAX_STORE_ITEMS:
                        _STORE.popitem(last=False)
        except Exception:
            pass

    # Load threads
    threads_path = persist_dir / _THREADS_FILE
    if threads_path.exists():
        try:
            with open(threads_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                with _THREADS_LOCK:
                    _THREADS.clear()
                    for k, v in data.items():
                        if isinstance(k, str) and isinstance(v, list):
                            _THREADS[k] = v[-_MAX_THREAD_ITEMS:]
                    # Trim to max size
                    while len(_THREADS) > _MAX_THREAD_RESPONSES:
                        _THREADS.popitem(last=False)
        except Exception:
            pass


def _save_store() -> None:
    """Persist store to disk."""
    if not _PERSISTENCE_ENABLED:
        return
    try:
        persist_dir = _get_persistence_dir()
        persist_dir.mkdir(parents=True, exist_ok=True)
        store_path = persist_dir / _STORE_FILE
        with _STORE_LOCK:
            data = dict(_STORE)
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _save_threads() -> None:
    """Persist threads to disk."""
    if not _PERSISTENCE_ENABLED:
        return
    try:
        persist_dir = _get_persistence_dir()
        persist_dir.mkdir(parents=True, exist_ok=True)
        threads_path = persist_dir / _THREADS_FILE
        with _THREADS_LOCK:
            data = dict(_THREADS)
        with open(threads_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


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
        _save_store()
    except Exception:
        pass


def _get_response(rid: str) -> Optional[Dict[str, Any]]:
    """Retrieve a stored response by ID."""
    with _STORE_LOCK:
        return _STORE.get(rid)


def _set_thread(rid: str, items: List[Dict[str, Any]]) -> None:
    """Store conversation thread for previous_response_id simulation (FIFO, bounded)."""
    try:
        if not (isinstance(rid, str) and rid and isinstance(items, list)):
            return
        trimmed = items[-_MAX_THREAD_ITEMS:]
        with _THREADS_LOCK:
            if rid in _THREADS:
                _THREADS.pop(rid, None)
            _THREADS[rid] = trimmed
            while len(_THREADS) > _MAX_THREAD_RESPONSES:
                _THREADS.popitem(last=False)
        _save_threads()
    except Exception:
        pass


def _get_thread(rid: str) -> Optional[List[Dict[str, Any]]]:
    """Get conversation thread for a response ID."""
    with _THREADS_LOCK:
        return _THREADS.get(rid)


# Load persisted data on module import
_load_persisted_data()


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
    """Remove upstream rs_* references from input items (recursive)."""
    REF_KEYS = {"previous_response_id", "response_id", "reference_id", "item_id"}

    def sanitize_obj(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                if (
                    isinstance(k, str)
                    and k in REF_KEYS
                    and isinstance(v, str)
                    and v.strip().startswith("rs_")
                ):
                    continue
                out[k] = sanitize_obj(v)
            return out
        if isinstance(obj, list):
            return [sanitize_obj(v) for v in obj]
        return obj

    result: List[Dict[str, Any]] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        result.append(sanitize_obj(it))
    return result


def _flatten_content_array(content: List[Any]) -> str:
    """Flatten a content array to a single string."""
    text_parts = []
    for part in content:
        if isinstance(part, dict):
            # Try various text fields
            for key in ("text", "content", "output", "result"):
                if key in part and isinstance(part[key], str):
                    text_parts.append(part[key])
                    break
            else:
                # No text field found, try to stringify
                ptype = part.get("type", "")
                if ptype in ("text", "input_text", "output_text"):
                    text_parts.append(str(part.get("text", "")))
        elif isinstance(part, str):
            text_parts.append(part)
    return "\n".join(text_parts) if text_parts else ""


class _NormalizationStats:
    """Track normalization changes for logging."""
    def __init__(self):
        self.reasoning_content_moved = 0
        self.reasoning_content_cleared = 0
        self.function_call_cleared = 0
        self.function_output_converted = 0
        self.tool_role_converted = 0
        self.message_content_normalized = 0

    def has_changes(self) -> bool:
        return any([
            self.reasoning_content_moved,
            self.reasoning_content_cleared,
            self.function_call_cleared,
            self.function_output_converted,
            self.tool_role_converted,
            self.message_content_normalized,
        ])

    def summary(self) -> str:
        parts = []
        if self.reasoning_content_moved:
            parts.append(f"reasoning:{self.reasoning_content_moved} moved to summary")
        if self.reasoning_content_cleared:
            parts.append(f"reasoning:{self.reasoning_content_cleared} cleared")
        if self.function_call_cleared:
            parts.append(f"function_call:{self.function_call_cleared} cleared")
        if self.function_output_converted:
            parts.append(f"function_output:{self.function_output_converted} converted")
        if self.tool_role_converted:
            parts.append(f"tool_role:{self.tool_role_converted} converted")
        if self.message_content_normalized:
            parts.append(f"messages:{self.message_content_normalized} normalized")
        return ", ".join(parts) if parts else "no changes"


def _normalize_content_for_upstream(items: List[Dict[str, Any]], debug: bool = False) -> List[Dict[str, Any]]:
    """Normalize content fields for ChatGPT upstream compatibility.

    Smart normalization that preserves data where possible:
    - reasoning: move content to summary (preserves reasoning text), clear content
    - function_call: content must be []
    - function_call_output: content -> output field
    - messages: normalize content types (input_text/output_text)

    Returns normalized items. Logs changes when debug=True.
    """
    result: List[Dict[str, Any]] = []
    stats = _NormalizationStats()

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        item = dict(item)  # shallow copy
        item_type = item.get("type")
        role = item.get("role")
        content = item.get("content")

        # function_call items: content must be empty array or absent
        if item_type == "function_call":
            if "content" in item and item["content"]:
                item["content"] = []
                stats.function_call_cleared += 1

        # reasoning items: preserve reasoning by moving to summary
        elif item_type == "reasoning":
            content_had_data = isinstance(content, list) and len(content) > 0

            if content_had_data:
                # Check if we have encrypted_content (preferred for multi-turn)
                has_encrypted = bool(item.get("encrypted_content"))

                # Extract text from reasoning_text items
                texts = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "reasoning_text":
                            texts.append(part.get("text", ""))
                        elif "text" in part:
                            texts.append(str(part.get("text", "")))

                # Move to summary if we have text and summary is empty/missing
                summary = item.get("summary", [])
                if texts and not summary:
                    combined_text = "".join(texts)
                    item["summary"] = [{"type": "summary_text", "text": combined_text}]
                    stats.reasoning_content_moved += 1
                    if debug:
                        preview = combined_text[:50] + "..." if len(combined_text) > 50 else combined_text
                        print(f"[normalize] item[{idx}] reasoning: moved {len(texts)} parts to summary: {preview!r}")
                else:
                    stats.reasoning_content_cleared += 1

            # Always clear content for reasoning (upstream requirement)
            item["content"] = []

        # function_call_output items: should use 'output', not 'content'
        elif item_type == "function_call_output":
            # If has content but no output, move content to output
            if "content" in item and "output" not in item:
                if isinstance(content, list):
                    item["output"] = _flatten_content_array(content)
                elif isinstance(content, str):
                    item["output"] = content
                del item["content"]
                stats.function_output_converted += 1
            elif "content" in item:
                del item["content"]
                stats.function_output_converted += 1

        # tool role (Chat Completions style): convert to function_call_output style
        elif role == "tool":
            if "type" not in item:
                item["type"] = "function_call_output"
            # Convert content to output
            if "content" in item and "output" not in item:
                if isinstance(content, list):
                    item["output"] = _flatten_content_array(content)
                elif isinstance(content, str):
                    item["output"] = content
                del item["content"]
                stats.tool_role_converted += 1
            elif "content" in item:
                del item["content"]
                stats.tool_role_converted += 1

        # message items with role: normalize content array
        elif role in ("user", "assistant", "system"):
            needs_normalization = False
            if isinstance(content, list):
                # Ensure content items have valid types
                normalized = []
                for part in content:
                    if isinstance(part, dict):
                        ptype = part.get("type", "")
                        # Convert chat-style types to responses-style
                        if ptype == "text":
                            if role == "assistant":
                                normalized.append({"type": "output_text", "text": part.get("text", "")})
                            else:
                                normalized.append({"type": "input_text", "text": part.get("text", "")})
                            needs_normalization = True
                        elif ptype in ("input_text", "output_text", "input_image", "refusal", "summary_text"):
                            normalized.append(part)
                        elif "text" in part:
                            # Unknown type but has text - convert
                            if role == "assistant":
                                normalized.append({"type": "output_text", "text": part.get("text", "")})
                            else:
                                normalized.append({"type": "input_text", "text": part.get("text", "")})
                            needs_normalization = True
                        else:
                            normalized.append(part)
                    elif isinstance(part, str):
                        if role == "assistant":
                            normalized.append({"type": "output_text", "text": part})
                        else:
                            normalized.append({"type": "input_text", "text": part})
                        needs_normalization = True
                item["content"] = normalized
                if needs_normalization:
                    stats.message_content_normalized += 1
            elif isinstance(content, str) and content:
                # String content - wrap in array
                if role == "assistant":
                    item["content"] = [{"type": "output_text", "text": content}]
                else:
                    item["content"] = [{"type": "input_text", "text": content}]
                stats.message_content_normalized += 1

        result.append(item)

    # Log normalization summary
    if debug and stats.has_changes():
        print(f"[normalize] {stats.summary()}")

    return result




def _instructions_for_model(model: str) -> str:
    """Get base instructions for a model."""
    base = current_app.config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if not isinstance(base, str) or not base.strip():
        base = "You are a helpful assistant."
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
    stream_req_raw = payload.get("stream")
    if stream_req_raw is None:
        stream_req = True
    elif isinstance(stream_req_raw, bool):
        stream_req = stream_req_raw
    elif isinstance(stream_req_raw, str):
        stream_req = stream_req_raw.strip().lower() not in ("0", "false", "no", "off")
    else:
        stream_req = bool(stream_req_raw)

    # Get and normalize model
    requested_model = payload.get("model")
    model = normalize_model_name(requested_model, debug_model)

    debug = bool(current_app.config.get("DEBUG_LOG"))
    if debug:
        print(f"[responses] {requested_model} -> {model}")
        # Log incoming payload keys for debugging
        print(f"[responses] payload keys: {list(payload.keys())}")

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

    # Handle previous_response_id or conversation_id (local threading simulation)
    prev_id = payload.get("previous_response_id") or payload.get("conversation_id")
    if isinstance(prev_id, str) and prev_id.strip():
        prior = _get_thread(prev_id.strip())
        if isinstance(prior, list) and prior:
            input_items = prior + input_items
        elif debug:
            print(f"[responses] previous_response_id '{prev_id}' not found in local store (session may have expired)")

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

    # Debug: dump tools conversion
    dump_tools_debug("responses", payload.get("tools"), tools_responses)

    # Handle instructions
    no_base = bool(current_app.config.get("RESPONSES_NO_BASE_INSTRUCTIONS"))
    base_inst = _instructions_for_model(model)
    user_inst = payload.get("instructions") if isinstance(payload.get("instructions"), str) else None

    # Check if client already sends official instructions (saves context tokens)
    client_has_official = has_official_instructions(user_inst)

    if no_base or client_has_official:
        # Use client's instructions directly (or fallback)
        instructions = user_inst.strip() if isinstance(user_inst, str) and user_inst.strip() else "You are a helpful assistant."
        if debug and client_has_official:
            print(f"[responses] client has official instructions, skipping base prompt")
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
    # NOT supported by ChatGPT internal API: metadata, user
    passthrough_keys = [
        "temperature", "top_p", "seed", "stop", "max_output_tokens", "truncation",
        "frequency_penalty", "presence_penalty", "service_tier", "logprobs", "top_logprobs",
    ]
    extra_fields: Dict[str, Any] = {}
    for k in passthrough_keys:
        if k in payload and payload.get(k) is not None:
            extra_fields[k] = payload.get(k)

    # Handle response_format → text.format conversion (for structured outputs)
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        rf_type = response_format.get("type")
        text_format: Dict[str, Any] = {}

        if rf_type == "text":
            text_format["type"] = "text"
        elif rf_type == "json_schema":
            text_format["type"] = "json_schema"
            json_schema = response_format.get("json_schema", {})
            if isinstance(json_schema, dict):
                if "name" in json_schema:
                    text_format["name"] = json_schema["name"]
                if "strict" in json_schema:
                    text_format["strict"] = json_schema["strict"]
                if "schema" in json_schema:
                    text_format["schema"] = json_schema["schema"]
        elif rf_type == "json_object":
            text_format["type"] = "json_object"

        if text_format:
            extra_fields["text"] = {"format": text_format}
            if debug:
                print(f"[responses] mapped response_format to text.format: {rf_type}")

    # Store flag for local use (not forwarded upstream)
    store_locally = bool(payload.get("store", False))

    # Shorten tool names if needed (64 char limit)
    tool_name_map = _build_tool_name_map(tools_responses)
    if tool_name_map:
        tools_responses = _apply_tool_name_shortening(tools_responses, tool_name_map)
        # Also shorten tool names referenced in input items (function_call items)
        input_items = _apply_tool_name_shortening_to_input(input_items, tool_name_map)
        if debug:
            print(f"[responses] shortened {len(tool_name_map)} tool names")

    # Normalize content fields for upstream compatibility
    input_items = _normalize_content_for_upstream(input_items, debug=debug)

    if debug:
        print(f"[responses] sending {len(input_items)} input items to upstream")

    # Dump full payload to JSON file when DEBUG_LOG is enabled
    dump_request(
        "responses",
        incoming=payload,
        outgoing={
            "model": model,
            "input": input_items,
            "instructions": instructions[:200] + "..." if isinstance(instructions, str) and len(instructions) > 200 else instructions,
            "tools": tools_responses,
            "tool_choice": tool_choice,
            "reasoning": reasoning_param,
            "extra_fields": extra_fields,
        },
    )

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
        error_msg = (
            (err_body.get("detail") if isinstance(err_body, dict) else None)
            or ((err_body.get("error", {}) or {}).get("message") if isinstance(err_body, dict) else None)
            or "Upstream error"
        )
        # Log error in debug mode
        if debug or verbose:
            print(f"[responses] ERROR {upstream.status_code}: {err_body}")
        # Retry once if upstream rejected an otherwise optional parameter (e.g. temperature).
        unsupported_param = None
        try:
            detail = err_body.get("detail") if isinstance(err_body, dict) else None
            if isinstance(detail, str) and detail.lower().startswith("unsupported parameter:"):
                unsupported_param = detail.split(":", 1)[1].strip()
        except Exception:
            unsupported_param = None

        if (
            isinstance(unsupported_param, str)
            and unsupported_param
            and isinstance(extra_fields, dict)
            and unsupported_param in extra_fields
        ):
            try:
                upstream.close()
            except Exception:
                pass
            extra_fields2 = dict(extra_fields)
            extra_fields2.pop(unsupported_param, None)
            print(f"[compat] /v1/responses retrying without unsupported param: {unsupported_param}")
            upstream_retry, err_retry = start_upstream_request(
                model,
                input_items,
                instructions=instructions,
                tools=tools_responses,
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
                extra_fields=extra_fields2,
            )
            if err_retry is None and upstream_retry is not None and upstream_retry.status_code < 400:
                record_rate_limits_from_response(upstream_retry)
                upstream = upstream_retry
                extra_fields = extra_fields2
            else:
                if upstream_retry is not None:
                    upstream = upstream_retry
                extra_fields = extra_fields2

        if upstream is not None and upstream.status_code < 400:
            pass
        else:
            return jsonify({"error": {"message": error_msg}}), upstream.status_code

    if stream_req:
        # Streaming mode - passthrough SSE events
        def _passthrough():
            stream_ok = True
            try:
                for chunk in upstream.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    yield chunk
            except (ChunkedEncodingError, ProtocolError, ConnectionError, ReadTimeout):
                stream_ok = False
                return
            except Exception:
                stream_ok = False
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
                            success=stream_ok,
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

    # Store response if requested (for retrieval via GET)
    if store_locally:
        _store_response(response_obj)

    # Always store thread for previous_response_id simulation (bounded FIFO)
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


@responses_bp.route("/v1/responses", methods=["GET"])
def responses_list() -> Response:
    """List responses endpoint - returns empty list (not supported).

    OpenAI doesn't support listing responses without an ID.
    This endpoint exists to handle GET /v1/responses gracefully.
    """
    resp = make_response(jsonify({"object": "list", "data": []}), 200)
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
def responses_options(**_kwargs) -> Response:
    """Handle CORS preflight requests."""
    resp = make_response("", 204)
    for k, v in build_cors_headers().items():
        resp.headers[k] = v
    return resp
