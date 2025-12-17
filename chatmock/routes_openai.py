from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request

from .config import (
    BASE_INSTRUCTIONS,
    GPT5_CODEX_INSTRUCTIONS,
    get_instructions_for_model,
    has_official_instructions,
)
from .debug import dump_prompt, dump_request, dump_tools_debug, debug_instructions_bisect, dump_upstream
from .limits import record_rate_limits_from_response
from .http import build_cors_headers
from .reasoning import (
    allowed_efforts_for_model,
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


def _wrap_stream_file_logging(iterator):
    """Wrap streaming iterator to collect and dump response to file.

    Enabled via DEBUG_LOG=true environment variable.
    Captures: text content, tool calls, finish reasons.
    """
    debug_enabled = any(
        os.getenv(v, "").lower() in ("1", "true", "yes", "on")
        for v in ("DEBUG_LOG", "CHATGPT_LOCAL_DEBUG", "CHATGPT_LOCAL_DEBUG_LOG")
    )
    if not debug_enabled:
        return iterator

    def _gen():
        accumulated_text = []
        tool_calls = []
        finish_reasons = []

        for chunk in iterator:
            # Parse chunk to extract data
            try:
                text = (
                    chunk.decode("utf-8", errors="replace")
                    if isinstance(chunk, (bytes, bytearray))
                    else str(chunk)
                )
                if text.startswith("data: ") and text.strip() != "data: [DONE]":
                    data_str = text[6:].strip()
                    if data_str:
                        evt = json.loads(data_str)
                        choices = evt.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            # Capture text content
                            if "content" in delta and delta["content"]:
                                accumulated_text.append(delta["content"])
                            # Capture tool calls
                            if "tool_calls" in delta:
                                for tc in delta["tool_calls"]:
                                    tc_id = tc.get("id", "")
                                    tc_func = tc.get("function", {})
                                    tc_name = tc_func.get("name", "")
                                    tc_args = tc_func.get("arguments", "")
                                    if tc_id and tc_name:
                                        # Find existing or add new
                                        existing = next((t for t in tool_calls if t["id"] == tc_id), None)
                                        if existing:
                                            existing["arguments"] += tc_args
                                        else:
                                            tool_calls.append({
                                                "id": tc_id,
                                                "name": tc_name,
                                                "arguments": tc_args
                                            })
                                    elif tc_args:  # Delta without id - append to last
                                        if tool_calls:
                                            tool_calls[-1]["arguments"] += tc_args
                            # Capture finish reason
                            fr = choices[0].get("finish_reason")
                            if fr:
                                finish_reasons.append(fr)
            except Exception:
                pass
            yield chunk

        # After stream ends, dump to file
        try:
            full_text = "".join(accumulated_text)
            dump_upstream(
                "chat_completions",
                {
                    "full_text": full_text[:2000] + "..." if len(full_text) > 2000 else full_text,
                    "full_text_length": len(full_text),
                    "tool_calls": tool_calls,
                    "tool_calls_count": len(tool_calls),
                    "finish_reasons": finish_reasons,
                    "stream": True,
                },
                label="upstream_response",
            )
        except Exception:
            pass

    return _gen()


def _instructions_for_model(model: str) -> str:
    base = current_app.config.get("BASE_INSTRUCTIONS", BASE_INSTRUCTIONS)
    if model.startswith("gpt-5-codex") or model.startswith("gpt-5.1-codex"):
        codex = current_app.config.get("GPT5_CODEX_INSTRUCTIONS") or GPT5_CODEX_INSTRUCTIONS
        if isinstance(codex, str) and codex.strip():
            return codex
    return base


@openai_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    from .routes_webui import record_request

    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")
    debug_model = current_app.config.get("DEBUG_MODEL")

    start_time = time.time()
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
    model = normalize_model_name(requested_model, debug_model)

    # Debug: log payload keys when DEBUG_LOG is enabled
    debug = bool(current_app.config.get("DEBUG_LOG"))
    if debug:
        print(f"[chat/completions] payload keys: {list(payload.keys())}")
        if not payload.get("messages"):
            print(f"[chat/completions] no messages, checking alternatives...")
            for k in ("input", "prompt", "conversation_id", "previous_response_id"):
                if payload.get(k):
                    print(f"[chat/completions] found {k}={type(payload.get(k)).__name__}")

    messages = payload.get("messages")
    if messages is None and isinstance(payload.get("prompt"), str):
        messages = [{"role": "user", "content": payload.get("prompt") or ""}]
    if messages is None and isinstance(payload.get("input"), str):
        messages = [{"role": "user", "content": payload.get("input") or ""}]
    # Support Responses API style input (list of items)
    if messages is None and isinstance(payload.get("input"), list):
        messages = payload.get("input")
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        err = {"error": {"message": "Request must include messages: []"}}
        if verbose:
            _log_json("OUT POST /v1/chat/completions", err)
        return jsonify(err), 400

    # Handle system prompt from client
    # If client sends official instructions (e.g., Cursor, Claude Code), use them directly
    # Otherwise, convert to user message and use ChatMock's base instructions
    client_system_prompt = None
    client_has_official = False
    log_prompts = os.environ.get("DEBUG_LOG_PROMPTS", "").lower() in ("1", "true", "yes")
    no_base = bool(current_app.config.get("RESPONSES_NO_BASE_INSTRUCTIONS"))
    if isinstance(messages, list):
        sys_idx = next((i for i, m in enumerate(messages) if isinstance(m, dict) and m.get("role") == "system"), None)
        if isinstance(sys_idx, int):
            sys_msg = messages.pop(sys_idx)
            content = sys_msg.get("content") if isinstance(sys_msg, dict) else ""
            client_system_prompt = content
            client_has_official = has_official_instructions(content)
            if debug:
                # Log first 500 chars of system prompt to see what Cursor sends
                preview = content[:500] if isinstance(content, str) else str(content)[:500]
                print(f"[chat/completions] CLIENT SYSTEM PROMPT ({len(content) if isinstance(content, str) else '?'} chars):\n{preview}...")
                if client_has_official:
                    print(f"[chat/completions] Client has official instructions - will use as instructions")
            if log_prompts and isinstance(content, str) and content:
                dump_prompt("client_system", content, prefix="cursor")
            # Only convert to user message if NOT using as instructions
            if not (no_base or client_has_official):
                messages.insert(0, {"role": "user", "content": content})
    is_stream = bool(payload.get("stream"))
    stream_options = payload.get("stream_options") if isinstance(payload.get("stream_options"), dict) else {}
    include_usage = bool(stream_options.get("include_usage", False))

    raw_tools = payload.get("tools")
    tools_responses = convert_tools_chat_to_responses(raw_tools)
    tool_choice = payload.get("tool_choice", "auto")

    # Debug: dump tools conversion for debugging MCP tools passthrough
    dump_tools_debug("chat_completions", raw_tools, tools_responses)
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))
    responses_tools_payload = payload.get("responses_tools") if isinstance(payload.get("responses_tools"), list) else []
    extra_tools: List[Dict[str, Any]] = []
    had_responses_tools = False
    if isinstance(responses_tools_payload, list):
        for _t in responses_tools_payload:
            if not (isinstance(_t, dict) and isinstance(_t.get("type"), str)):
                continue
            if _t.get("type") not in ("web_search", "web_search_preview"):
                err = {
                    "error": {
                        "message": "Only web_search/web_search_preview are supported in responses_tools",
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
            {"role": "user", "content": [{"type": "input_text", "text": payload.get("prompt")}]}
        ]

    # Support previous_response_id / conversation_id (get history from local store)
    prev_id = payload.get("previous_response_id") or payload.get("conversation_id")
    if isinstance(prev_id, str) and prev_id.strip():
        try:
            from .routes_responses import _get_thread
            prior = _get_thread(prev_id.strip())
            if isinstance(prior, list) and prior:
                input_items = prior + (input_items or [])
                if debug:
                    print(f"[chat/completions] loaded {len(prior)} items from previous_response_id={prev_id}")
            elif debug:
                print(f"[chat/completions] previous_response_id={prev_id} not found in local store")
        except ImportError:
            if debug:
                print(f"[chat/completions] previous_response_id support unavailable (routes_responses not loaded)")

    # Debug: log when input_items is empty
    if debug and not input_items:
        print(f"[chat/completions] WARNING: input_items empty after conversion")
        print(f"[chat/completions] messages count={len(messages)}, messages={messages[:2] if messages else 'empty'}...")

    # Fallback: if still empty but we have messages with content, try direct pass
    if not input_items and messages:
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content")
                role = msg.get("role", "user")
                if role == "system":
                    role = "user"
                if isinstance(content, str) and content.strip():
                    input_items.append({
                        "role": role if role in ("user", "assistant") else "user",
                        "content": [{"type": "input_text" if role != "assistant" else "output_text", "text": content}]
                    })
                elif isinstance(content, list) and content:
                    # Pass through as-is if it's already structured
                    input_items.append({"role": role if role in ("user", "assistant") else "user", "content": content})
        if debug and input_items:
            print(f"[chat/completions] fallback produced {len(input_items)} items")

    # Final check: reject if still no input
    if not input_items:
        err = {
            "error": {
                "message": "Request must include non-empty 'messages', 'input', or 'prompt'",
                "code": "EMPTY_INPUT",
            }
        }
        if debug or verbose:
            print(f"[chat/completions] ERROR: no input items, payload keys={list(payload.keys())}")
            if verbose:
                _log_json("OUT POST /v1/chat/completions", err)
        return jsonify(err), 400

    model_reasoning = extract_reasoning_from_model_name(requested_model)
    reasoning_overrides = payload.get("reasoning") if isinstance(payload.get("reasoning"), dict) else model_reasoning
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )

    # Extract passthrough fields (temperature, top_p, etc.)
    # NOT supported by ChatGPT internal API: metadata, user
    passthrough_keys = [
        "temperature", "top_p", "seed", "stop", "max_output_tokens", "truncation",
        "frequency_penalty", "presence_penalty", "service_tier", "logprobs", "top_logprobs",
    ]
    extra_fields: Dict[str, Any] = {}
    for k in passthrough_keys:
        if k in payload and payload.get(k) is not None:
            extra_fields[k] = payload.get(k)

    # Handle max_tokens → max_output_tokens mapping (Chat Completions uses max_tokens)
    if "max_tokens" in payload and payload.get("max_tokens") is not None:
        extra_fields["max_output_tokens"] = payload.get("max_tokens")
    if "max_completion_tokens" in payload and payload.get("max_completion_tokens") is not None:
        extra_fields["max_output_tokens"] = payload.get("max_completion_tokens")

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
                print(f"[chat/completions] mapped response_format to text.format: {rf_type}")

    # Debug: dump full request before sending upstream
    dump_request(
        "chat_completions",
        incoming=payload,
        outgoing={
            "model": model,
            "input_items_count": len(input_items),
            "tools_count": len(tools_responses) if tools_responses else 0,
            "tool_choice": tool_choice,
            "reasoning": reasoning_param,
            "extra_fields": extra_fields,
        },
        extra={"requested_model": requested_model},
    )

    # Determine which instructions to use
    # GPT-5.2 and similar models have strict instruction validation - they only accept
    # whitelisted instruction formats. We use model-specific prompts from official Codex.
    # Client system prompt goes as a separate developer message (like official Codex does).
    model_needs_base_instructions = model.startswith("gpt-5.2")

    if model_needs_base_instructions:
        # GPT-5.2: Use model-specific instructions in 'instructions' field (validated by API)
        # Client system prompt goes as a separate developer message (like official Codex does)
        final_instructions = get_instructions_for_model(model)
        if client_system_prompt and isinstance(client_system_prompt, str) and client_system_prompt.strip():
            # Send client prompt as developer message (higher authority than user messages)
            client_as_developer = {
                "type": "message",
                "role": "developer",
                "content": [{"type": "input_text", "text": client_system_prompt.strip()}]
            }
            input_items = [client_as_developer] + input_items
            if debug:
                print(f"[chat/completions] GPT-5.2: Using {len(final_instructions)} char model instructions + {len(client_system_prompt)} char client prompt as developer message")
        else:
            if debug:
                print(f"[chat/completions] GPT-5.2: Using model-specific instructions ({len(final_instructions)} chars)")
    elif no_base or client_has_official:
        # Use client's instructions directly (or fallback)
        final_instructions = client_system_prompt.strip() if isinstance(client_system_prompt, str) and client_system_prompt.strip() else "You are a helpful assistant."
        if debug:
            print(f"[chat/completions] Using CLIENT instructions ({len(final_instructions)} chars)")
    else:
        final_instructions = _instructions_for_model(model)
        if debug:
            print(f"[chat/completions] Using CHATMOCK instructions ({len(final_instructions)} chars)")
            if client_system_prompt:
                print(f"[chat/completions] Client system prompt ({len(client_system_prompt)} chars) was converted to user message")

    if debug:
        inst_preview = final_instructions[:300] if isinstance(final_instructions, str) else str(final_instructions)[:300]
        print(f"[chat/completions] FINAL INSTRUCTIONS preview:\n{inst_preview}...")
    if log_prompts and isinstance(final_instructions, str) and final_instructions:
        dump_prompt("final_instructions", final_instructions, prefix="chatmock")

    # =========================================================================
    # DEBUG INSTRUCTIONS BISECT
    # Enable via DEBUG_INSTRUCTIONS_BISECT=1 to find which tagged block causes
    # "Instructions are not valid" error. Sends iterative requests, removing
    # one block at a time until upstream accepts.
    # =========================================================================
    if os.getenv("DEBUG_INSTRUCTIONS_BISECT", "").lower() in ("1", "true", "yes", "on"):
        def _test_instructions(test_inst: str) -> tuple:
            """Send test request and return (status_code, error_message)."""
            test_upstream, test_err = start_upstream_request(
                model,
                input_items,
                instructions=test_inst,
                tools=tools_responses,
                tool_choice=tool_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
                extra_fields=extra_fields,
            )
            if test_err is not None:
                try:
                    body = test_err.get_data(as_text=True)
                    return (test_err.status_code or 500, body)
                except Exception:
                    return (500, "Unknown error")
            if test_upstream is None:
                return (500, "No upstream response")
            if test_upstream.status_code >= 400:
                try:
                    raw = test_upstream.text
                    err = json.loads(raw) if raw else {}
                    msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                    return (test_upstream.status_code, msg)
                except Exception as e:
                    return (test_upstream.status_code, str(e))
            return (test_upstream.status_code, "")

        # First, test with minimal instructions to see if problem is elsewhere
        print("[debug_bisect] Testing with minimal instructions first...")
        minimal_test = "You are a helpful assistant."
        min_status, min_err = _test_instructions(minimal_test)
        print(f"[debug_bisect] Minimal instructions test: status={min_status}, error={min_err[:100] if min_err else 'none'}")

        if min_status >= 400:
            # Even minimal instructions fail - problem is NOT in instructions content
            # Try with empty instructions
            print("[debug_bisect] Minimal failed! Trying empty instructions...")
            empty_status, empty_err = _test_instructions("")
            print(f"[debug_bisect] Empty instructions test: status={empty_status}, error={empty_err[:100] if empty_err else 'none'}")

            if empty_status >= 400:
                print("[debug_bisect] CONCLUSION: Problem is NOT in instructions - checking tools!")
                # Bisect tools instead!
                if tools_responses:
                    print(f"[debug_bisect] Testing {len(tools_responses)} tools...")

                    def _test_with_tools(test_tools):
                        """Test request with specific tools."""
                        test_upstream, test_err = start_upstream_request(
                            model,
                            input_items,
                            instructions=minimal_test,
                            tools=test_tools,
                            tool_choice=tool_choice,
                            parallel_tool_calls=parallel_tool_calls,
                            reasoning_param=reasoning_param,
                            extra_fields=extra_fields,
                        )
                        if test_err is not None:
                            return (500, "error_resp")
                        if test_upstream is None:
                            return (500, "no response")
                        if test_upstream.status_code >= 400:
                            try:
                                raw = test_upstream.text
                                err = json.loads(raw) if raw else {}
                                msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                                return (test_upstream.status_code, msg)
                            except Exception as e:
                                return (test_upstream.status_code, str(e))
                        return (test_upstream.status_code, "")

                    # First test with NO tools
                    print("[debug_bisect] Testing with NO tools...")
                    no_tools_status, no_tools_err = _test_with_tools([])
                    print(f"[debug_bisect] No tools: status={no_tools_status}, error={no_tools_err[:100] if no_tools_err else 'none'}")

                    if no_tools_status < 400:
                        # No tools works! Find the bad tool by binary search
                        print("[debug_bisect] No tools WORKS! Binary searching for bad tool...")
                    else:
                        # Even no tools fails - try with BASE_INSTRUCTIONS
                        print("[debug_bisect] Even NO tools fails - trying BASE_INSTRUCTIONS...")
                        base_status, base_err = _test_with_tools([])
                        # Temporarily patch to use BASE_INSTRUCTIONS
                        def _test_base_instructions():
                            test_upstream, test_err = start_upstream_request(
                                model,
                                input_items,
                                instructions=BASE_INSTRUCTIONS,
                                tools=[],
                                tool_choice=tool_choice,
                                parallel_tool_calls=parallel_tool_calls,
                                reasoning_param=reasoning_param,
                                extra_fields=extra_fields,
                            )
                            if test_err is not None:
                                return (500, "error_resp")
                            if test_upstream is None:
                                return (500, "no response")
                            if test_upstream.status_code >= 400:
                                try:
                                    raw = test_upstream.text
                                    err = json.loads(raw) if raw else {}
                                    msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                                    return (test_upstream.status_code, msg)
                                except Exception as e:
                                    return (test_upstream.status_code, str(e))
                            return (test_upstream.status_code, "")

                        base_inst_status, base_inst_err = _test_base_instructions()
                        print(f"[debug_bisect] BASE_INSTRUCTIONS test: status={base_inst_status}, error={base_inst_err[:100] if base_inst_err else 'none'}")

                        if base_inst_status < 400:
                            print("[debug_bisect] BASE_INSTRUCTIONS WORKS! Problem is instruction format/content!")
                            print(f"[debug_bisect] BASE_INSTRUCTIONS preview: {BASE_INSTRUCTIONS[:200]}...")

                            # Try replacing just the first line of client instructions
                            print("[debug_bisect] Trying to replace first line of client prompt with BASE first line...")
                            base_first_line = BASE_INSTRUCTIONS.split('\n')[0]
                            client_lines = final_instructions.split('\n')
                            if client_lines:
                                client_lines[0] = base_first_line
                                hybrid_instructions = '\n'.join(client_lines)

                                def _test_hybrid():
                                    test_upstream, test_err = start_upstream_request(
                                        model,
                                        input_items,
                                        instructions=hybrid_instructions,
                                        tools=tools_responses,
                                        tool_choice=tool_choice,
                                        parallel_tool_calls=parallel_tool_calls,
                                        reasoning_param=reasoning_param,
                                        extra_fields=extra_fields,
                                    )
                                    if test_err is not None:
                                        return (500, "error_resp")
                                    if test_upstream is None:
                                        return (500, "no response")
                                    if test_upstream.status_code >= 400:
                                        try:
                                            raw = test_upstream.text
                                            err = json.loads(raw) if raw else {}
                                            msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                                            return (test_upstream.status_code, msg)
                                        except Exception as e:
                                            return (test_upstream.status_code, str(e))
                                    return (test_upstream.status_code, "")

                                hybrid_status, hybrid_err = _test_hybrid()
                                print(f"[debug_bisect] Hybrid (BASE first line + client rest): status={hybrid_status}, error={hybrid_err[:100] if hybrid_err else 'none'}")

                                if hybrid_status < 400:
                                    print("[debug_bisect] HYBRID WORKS! Just need to replace first line!")
                                    print(f"[debug_bisect] Using hybrid instructions ({len(hybrid_instructions)} chars)")
                                    final_instructions = hybrid_instructions
                                else:
                                    print("[debug_bisect] Hybrid (first line) failed - trying BASE as prefix...")

                                    # Try prepending full BASE_INSTRUCTIONS
                                    prefixed_instructions = BASE_INSTRUCTIONS + "\n\n---\n\n" + final_instructions

                                    def _test_prefixed():
                                        test_upstream, test_err = start_upstream_request(
                                            model,
                                            input_items,
                                            instructions=prefixed_instructions,
                                            tools=tools_responses,
                                            tool_choice=tool_choice,
                                            parallel_tool_calls=parallel_tool_calls,
                                            reasoning_param=reasoning_param,
                                            extra_fields=extra_fields,
                                        )
                                        if test_err is not None:
                                            return (500, "error_resp")
                                        if test_upstream is None:
                                            return (500, "no response")
                                        if test_upstream.status_code >= 400:
                                            try:
                                                raw = test_upstream.text
                                                err = json.loads(raw) if raw else {}
                                                msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                                                return (test_upstream.status_code, msg)
                                            except Exception as e:
                                                return (test_upstream.status_code, str(e))
                                        return (test_upstream.status_code, "")

                                    prefixed_status, prefixed_err = _test_prefixed()
                                    print(f"[debug_bisect] Prefixed (BASE + client): status={prefixed_status}, error={prefixed_err[:100] if prefixed_err else 'none'}")

                                    if prefixed_status < 400:
                                        print(f"[debug_bisect] PREFIXED WORKS! Using ({len(prefixed_instructions)} chars)")
                                        final_instructions = prefixed_instructions
                                    else:
                                        print("[debug_bisect] Prefixed also failed - using model instructions + developer message")
                                        # FALLBACK: Use model instructions, client prompt as developer message
                                        final_instructions = get_instructions_for_model(model)
                                        if client_system_prompt and isinstance(client_system_prompt, str) and client_system_prompt.strip():
                                            client_as_developer = {
                                                "type": "message",
                                                "role": "developer",
                                                "content": [{"type": "input_text", "text": client_system_prompt.strip()}]
                                            }
                                            input_items = [client_as_developer] + input_items
                                            print(f"[debug_bisect] FALLBACK: Using model instructions + client prompt as developer message")
                                        else:
                                            print(f"[debug_bisect] FALLBACK: Using model instructions only ({len(final_instructions)} chars)")
                        else:
                            print("[debug_bisect] BASE_INSTRUCTIONS also fails - problem in input_items format!")
                            # Try with empty input to confirm
                            def _test_empty_input():
                                test_upstream, test_err = start_upstream_request(
                                    model,
                                    [],  # Empty input
                                    instructions=BASE_INSTRUCTIONS,
                                    tools=[],
                                    tool_choice=tool_choice,
                                    parallel_tool_calls=parallel_tool_calls,
                                    reasoning_param=reasoning_param,
                                    extra_fields=extra_fields,
                                )
                                if test_err is not None:
                                    return (500, "error_resp")
                                if test_upstream is None:
                                    return (500, "no response")
                                if test_upstream.status_code >= 400:
                                    try:
                                        raw = test_upstream.text
                                        err = json.loads(raw) if raw else {}
                                        msg = err.get("detail") or err.get("error", {}).get("message", raw[:200])
                                        return (test_upstream.status_code, msg)
                                    except Exception as e:
                                        return (test_upstream.status_code, str(e))
                                return (test_upstream.status_code, "")

                            empty_input_status, empty_input_err = _test_empty_input()
                            print(f"[debug_bisect] Empty input test: status={empty_input_status}, error={empty_input_err[:100] if empty_input_err else 'none'}")

                            if empty_input_status < 400:
                                print("[debug_bisect] Empty input WORKS! Problem is in input_items content!")
                                # Log first few input items for debugging
                                print(f"[debug_bisect] First input item: {json.dumps(input_items[0] if input_items else {})[:500]}")
                            else:
                                print("[debug_bisect] Even empty input fails - problem in other params (model, reasoning, etc.)")
            else:
                print("[debug_bisect] Empty works but minimal doesn't - very strange!")
        else:
            print("[debug_bisect] Minimal instructions WORK - running bisect to find problematic block...")
            working_inst, report_path = debug_instructions_bisect(
                final_instructions,
                _test_instructions,
                model=model,
            )
            if working_inst is not None:
                print(f"[chat/completions] DEBUG BISECT: Using working instructions ({len(working_inst)} chars)")
                final_instructions = working_inst
    # =========================================================================
    # END DEBUG INSTRUCTIONS BISECT
    # =========================================================================

    # Debug: dump full upstream payload before sending
    dump_upstream(
        "chat_completions",
        {
            "model": model,
            "instructions": final_instructions[:500] + "..." if len(final_instructions or "") > 500 else final_instructions,
            "input_items": input_items,
            "tools_count": len(tools_responses) if tools_responses else 0,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning_param,
            "extra_fields": extra_fields,
        },
        label="upstream_request",
    )

    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=final_instructions,
        tools=tools_responses,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel_tool_calls,
        reasoning_param=reasoning_param,
        extra_fields=extra_fields,
    )
    if error_resp is not None:
        response_time = time.time() - start_time
        error_msg = "Upstream request failed"
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                        error_msg = parsed.get("error", {}).get("message", error_msg) if isinstance(parsed, dict) else error_msg
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/chat/completions", parsed)
            except Exception:
                pass
        record_request(
            model=requested_model or model,
            endpoint="openai/chat/completions",
            success=False,
            response_time=response_time,
            error_message=error_msg,
        )
        return error_resp

    record_rate_limits_from_response(upstream)

    created = int(time.time())
    if upstream.status_code >= 400:
        # For streaming responses, read the full content
        try:
            # Try .text first (works better for error responses)
            raw_text = upstream.text
            if raw_text:
                err_body = json.loads(raw_text)
            else:
                err_body = {"raw": f"Empty response, status={upstream.status_code}"}
        except json.JSONDecodeError:
            err_body = {"raw": raw_text[:500] if raw_text else "No content"}
        except Exception as e:
            err_body = {"raw": f"Error reading response: {e}"}
        # Always log upstream error for debugging
        # ChatGPT API returns {"detail": "..."} format, not {"error": {"message": "..."}}
        upstream_err_msg = (
            err_body.get("detail")  # ChatGPT format
            or (err_body.get("error", {}) or {}).get("message")  # OpenAI format
            or err_body.get("raw", "Unknown error")
        )
        print(f"[chat/completions] Upstream error ({upstream.status_code}): {upstream_err_msg}")
        if debug:
            _log_json("[chat/completions] Full upstream error", err_body)
        if had_responses_tools:
            if verbose:
                print("[Passthrough] Upstream rejected tools; retrying without extra tools (args redacted)")
            base_tools_only = convert_tools_chat_to_responses(payload.get("tools"))
            safe_choice = payload.get("tool_choice", "auto")
            upstream2, err2 = start_upstream_request(
                model,
                input_items,
                instructions=final_instructions,  # Use same instructions as first attempt
                tools=base_tools_only,
                tool_choice=safe_choice,
                parallel_tool_calls=parallel_tool_calls,
                reasoning_param=reasoning_param,
                extra_fields=extra_fields,
            )
            record_rate_limits_from_response(upstream2)
            if err2 is None and upstream2 is not None and upstream2.status_code < 400:
                upstream = upstream2
            else:
                # Retry also failed - log the second error
                if upstream2 is not None:
                    try:
                        raw_text2 = upstream2.text
                        if raw_text2:
                            err_body2 = json.loads(raw_text2)
                            retry_err_msg = (
                                err_body2.get("detail")  # ChatGPT format
                                or (err_body2.get("error", {}) or {}).get("message")  # OpenAI format
                                or raw_text2[:200]
                            )
                        else:
                            retry_err_msg = f"Empty response, status={upstream2.status_code}"
                        print(f"[chat/completions] Retry also failed ({upstream2.status_code}): {retry_err_msg}")
                    except Exception as e:
                        print(f"[chat/completions] Retry failed ({upstream2.status_code}), error parsing: {e}")
                err = {
                    "error": {
                        "message": upstream_err_msg,
                        "code": "RESPONSES_TOOLS_REJECTED",
                    }
                }
                if verbose:
                    _log_json("OUT POST /v1/chat/completions", err)
                response_time = time.time() - start_time
                record_request(
                    model=requested_model or model,
                    endpoint="openai/chat/completions",
                    success=False,
                    response_time=response_time,
                    error_message=err["error"]["message"],
                )
                return jsonify(err), (upstream2.status_code if upstream2 is not None else upstream.status_code)
        else:
            if verbose:
                print("Upstream error status=", upstream.status_code)
            err = {"error": {"message": (err_body.get("error", {}) or {}).get("message", "Upstream error")}}
            if verbose:
                _log_json("OUT POST /v1/chat/completions", err)
            response_time = time.time() - start_time
            record_request(
                model=requested_model or model,
                endpoint="openai/chat/completions",
                success=False,
                response_time=response_time,
                error_message=err["error"]["message"],
            )
            return jsonify(err), upstream.status_code

    if is_stream:
        if verbose:
            print("OUT POST /v1/chat/completions (streaming response)")

        # Record streaming request (without token counts as they're not available yet)
        response_time = time.time() - start_time
        record_request(
            model=requested_model or model,
            endpoint="openai/chat/completions/stream",
            success=True,
            response_time=response_time,
        )

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
        stream_iter = _wrap_stream_file_logging(stream_iter)  # File-based debug logging
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

    if error_message:
        response_time = time.time() - start_time
        record_request(
            model=requested_model or model,
            endpoint="openai/chat/completions",
            success=False,
            response_time=response_time,
            error_message=error_message,
        )
        resp = make_response(jsonify({"error": {"message": error_message}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    # Debug: dump upstream response (what ChatGPT returned)
    dump_upstream(
        "chat_completions",
        {
            "full_text": full_text[:500] + "..." if len(full_text or "") > 500 else full_text,
            "tool_calls": tool_calls,
            "tool_calls_count": len(tool_calls) if tool_calls else 0,
            "reasoning_summary": reasoning_summary_text[:200] + "..." if len(reasoning_summary_text or "") > 200 else reasoning_summary_text,
            "response_id": response_id,
            "usage": usage_obj,
        },
        label="upstream_response",
    )

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
    if verbose:
        _log_json("OUT POST /v1/chat/completions", completion)

    # Record statistics
    response_time = time.time() - start_time
    record_request(
        model=requested_model or model,
        endpoint="openai/chat/completions",
        success=True,
        prompt_tokens=usage_obj.get("prompt_tokens", 0) if usage_obj else 0,
        completion_tokens=usage_obj.get("completion_tokens", 0) if usage_obj else 0,
        total_tokens=usage_obj.get("total_tokens", 0) if usage_obj else 0,
        response_time=response_time,
    )

    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/completions", methods=["POST"])
def completions() -> Response:
    from .routes_webui import record_request

    verbose = bool(current_app.config.get("VERBOSE"))
    verbose_obfuscation = bool(current_app.config.get("VERBOSE_OBFUSCATION"))
    debug_model = current_app.config.get("DEBUG_MODEL")
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")

    start_time = time.time()
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
    reasoning_param = build_reasoning_param(
        reasoning_effort,
        reasoning_summary,
        reasoning_overrides,
        allowed_efforts=allowed_efforts_for_model(model),
    )
    upstream, error_resp = start_upstream_request(
        model,
        input_items,
        instructions=_instructions_for_model(model),
        reasoning_param=reasoning_param,
    )
    if error_resp is not None:
        response_time = time.time() - start_time
        error_msg = "Upstream request failed"
        if verbose:
            try:
                body = error_resp.get_data(as_text=True)
                if body:
                    try:
                        parsed = json.loads(body)
                        error_msg = parsed.get("error", {}).get("message", error_msg) if isinstance(parsed, dict) else error_msg
                    except Exception:
                        parsed = body
                    _log_json("OUT POST /v1/completions", parsed)
            except Exception:
                pass
        record_request(
            model=requested_model or model,
            endpoint="openai/completions",
            success=False,
            response_time=response_time,
            error_message=error_msg,
        )
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
        response_time = time.time() - start_time
        record_request(
            model=requested_model or model,
            endpoint="openai/completions",
            success=False,
            response_time=response_time,
            error_message=err["error"]["message"],
        )
        return jsonify(err), upstream.status_code

    if stream_req:
        if verbose:
            print("OUT POST /v1/completions (streaming response)")

        # Record streaming request (without token counts as they're not available yet)
        response_time = time.time() - start_time
        record_request(
            model=requested_model or model,
            endpoint="openai/completions/stream",
            success=True,
            response_time=response_time,
        )

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

    # Record statistics
    response_time = time.time() - start_time
    record_request(
        model=requested_model or model,
        endpoint="openai/completions",
        success=True,
        prompt_tokens=usage_obj.get("prompt_tokens", 0) if usage_obj else 0,
        completion_tokens=usage_obj.get("completion_tokens", 0) if usage_obj else 0,
        total_tokens=usage_obj.get("total_tokens", 0) if usage_obj else 0,
        response_time=response_time,
    )

    resp = make_response(jsonify(completion), upstream.status_code)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp


@openai_bp.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    from .config import get_model_ids
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    expose_experimental = bool(current_app.config.get("EXPOSE_EXPERIMENTAL_MODELS"))
    model_ids = get_model_ids(expose_variants, expose_experimental)
    data = [{"id": mid, "object": "model", "owned_by": "owner"} for mid in model_ids]
    models = {"object": "list", "data": data}
    resp = make_response(jsonify(models), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp
