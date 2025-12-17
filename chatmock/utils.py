from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import secrets
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests

from .config import CLIENT_ID_DEFAULT, OAUTH_TOKEN_URL


def eprint(*args, **kwargs) -> None:
    print(*args, file=sys.stderr, **kwargs)


def get_home_dir() -> str:
    home = os.getenv("CHATGPT_LOCAL_HOME") or os.getenv("CODEX_HOME")
    if not home:
        home = os.path.expanduser("~/.chatgpt-local")
    return home


def read_auth_file() -> Dict[str, Any] | None:
    for base in [
        os.getenv("CHATGPT_LOCAL_HOME"),
        os.getenv("CODEX_HOME"),
        os.path.expanduser("~/.chatgpt-local"),
        os.path.expanduser("~/.codex"),
    ]:
        if not base:
            continue
        path = os.path.join(base, "auth.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None


def write_auth_file(auth: Dict[str, Any]) -> bool:
    home = get_home_dir()
    try:
        os.makedirs(home, exist_ok=True)
    except Exception as exc:
        eprint(f"ERROR: unable to create auth home directory {home}: {exc}")
        return False
    path = os.path.join(home, "auth.json")
    try:
        with open(path, "w", encoding="utf-8") as fp:
            if hasattr(os, "fchmod"):
                os.fchmod(fp.fileno(), 0o600)
            json.dump(auth, fp, indent=2)
        return True
    except Exception as exc:
        eprint(f"ERROR: unable to write auth file: {exc}")
        return False


def parse_jwt_claims(token: str) -> Dict[str, Any] | None:
    if not token or token.count(".") != 2:
        return None
    try:
        _, payload, _ = token.split(".")
        padded = payload + "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(padded.encode())
        return json.loads(data.decode())
    except Exception:
        return None


def generate_pkce() -> "PkceCodes":
    from .models import PkceCodes

    code_verifier = secrets.token_hex(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return PkceCodes(code_verifier=code_verifier, code_challenge=code_challenge)


def convert_chat_messages_to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _normalize_image_data_url(url: str) -> str:
        try:
            if not isinstance(url, str):
                return url
            if not url.startswith("data:image/"):
                return url
            if ";base64," not in url:
                return url
            header, data = url.split(",", 1)
            try:
                from urllib.parse import unquote

                data = unquote(data)
            except Exception:
                pass
            data = data.strip().replace("\n", "").replace("\r", "")
            data = data.replace("-", "+").replace("_", "/")
            pad = (-len(data)) % 4
            if pad:
                data = data + ("=" * pad)
            try:
                base64.b64decode(data, validate=True)
            except Exception:
                return url
            return f"{header},{data}"
        except Exception:
            return url

    input_items: List[Dict[str, Any]] = []
    seen_function_call_ids: set[str] = set()
    debug_tools = bool(os.getenv("CHATMOCK_DEBUG_TOOLS"))

    # Known Responses API item types that should be passed through directly
    # Cursor sends mixed format: Chat messages (with role) + Responses API items (with type)
    _responses_api_types = {"function_call", "function_call_output", "message", "item_reference"}

    for message in messages:
        # Passthrough for items already in Responses API format (type field, no role or role inside)
        msg_type = message.get("type")
        if isinstance(msg_type, str) and msg_type in _responses_api_types:
            # Track function_call IDs for later matching
            if msg_type == "function_call":
                call_id = message.get("call_id")
                if isinstance(call_id, str):
                    seen_function_call_ids.add(call_id)
            # For function_call_output, only include if we've seen the matching function_call
            elif msg_type == "function_call_output":
                call_id = message.get("call_id")
                if isinstance(call_id, str) and call_id not in seen_function_call_ids:
                    if debug_tools:
                        try:
                            eprint(
                                f"[CHATMOCK_DEBUG_TOOLS] passthrough: function_call_output without matching function_call: call_id={call_id!r}"
                            )
                        except Exception:
                            pass
                    continue
            input_items.append(message)
            continue

        role = message.get("role")
        if role == "system":
            continue

        if role == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
            # Debug: log tool result processing
            try:
                content_preview = str(message.get("content", ""))[:200]
                print(f"[TOOL_RESULT] Processing role=tool: call_id={call_id!r} content={content_preview!r}")
                print(f"[TOOL_RESULT] seen_function_call_ids={seen_function_call_ids}")
            except Exception:
                pass
            if isinstance(call_id, str) and call_id:
                content = message.get("content", "")
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict):
                            t = part.get("text") or part.get("content")
                            if isinstance(t, str) and t:
                                texts.append(t)
                    content = "\n".join(texts)
                if isinstance(content, str):
                    if call_id not in seen_function_call_ids:
                        # Debug: log skipped tool result
                        try:
                            print(f"[TOOL_RESULT] SKIPPED! call_id={call_id!r} not in seen_function_call_ids")
                        except Exception:
                            pass
                        if debug_tools:
                            try:
                                eprint(
                                    f"[CHATMOCK_DEBUG_TOOLS] function_call_output without matching function_call: call_id={call_id!r}"
                                )
                            except Exception:
                                pass
                        # Не отправляем function_call_output без соответствующего function_call.
                        # Это предотвращает 400 от Responses: "No tool call found for function call output".
                        continue
                    # Debug: log accepted tool result
                    try:
                        print(f"[TOOL_RESULT] ACCEPTED: call_id={call_id!r} -> function_call_output")
                    except Exception:
                        pass
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": content,
                        }
                    )
            continue
        if role == "assistant" and isinstance(message.get("tool_calls"), list):
            for tc in message.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                tc_type = tc.get("type", "function")
                if tc_type != "function":
                    continue
                call_id = tc.get("id") or tc.get("call_id")
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = fn.get("name") if isinstance(fn, dict) else None
                args = fn.get("arguments") if isinstance(fn, dict) else None
                if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                    if isinstance(call_id, str):
                        seen_function_call_ids.add(call_id)
                    input_items.append(
                        {
                            "type": "function_call",
                            "name": name,
                            "arguments": args,
                            "call_id": call_id,
                        }
                    )

        content = message.get("content", "")
        content_items: List[Dict[str, Any]] = []
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text") or part.get("content") or ""
                    if isinstance(text, str) and text:
                        kind = "output_text" if role == "assistant" else "input_text"
                        content_items.append({"type": kind, "text": text})
                elif ptype == "image_url":
                    image = part.get("image_url")
                    url = image.get("url") if isinstance(image, dict) else image
                    if isinstance(url, str) and url:
                        content_items.append({"type": "input_image", "image_url": _normalize_image_data_url(url)})
        elif isinstance(content, str) and content:
            kind = "output_text" if role == "assistant" else "input_text"
            content_items.append({"type": kind, "text": content})

        if not content_items:
            continue
        role_out = "assistant" if role == "assistant" else "user"
        # Note: No "type": "message" - upstream Responses API doesn't accept it
        input_items.append({"role": role_out, "content": content_items})
    return input_items


def convert_tools_chat_to_responses(tools: Any) -> List[Dict[str, Any]]:
    """Convert tools from Chat Completions format to Responses API format.

    Handles multiple formats:
    - Nested (Chat Completions): {type: "function", function: {name, description, parameters}}
    - Flat (Responses API / Cursor): {type: "function", name, description, parameters}
    - Custom (Cursor grammar-based): {type: "custom", name, description, format: {...}}
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(tools, list):
        return out
    for t in tools:
        if not isinstance(t, dict):
            continue

        tool_type = t.get("type")

        # Handle custom tools (e.g., apply_patch with Lark grammar)
        # Pass through as-is since Responses API natively supports type: "custom"
        # These return custom_tool_call items with raw 'input' string (not JSON arguments)
        # See: https://platform.openai.com/docs/guides/tools#custom-tools
        if tool_type == "custom":
            name = t.get("name")
            if isinstance(name, str) and name:
                # Pass through the entire custom tool definition unchanged
                out.append(t)
            continue

        if tool_type != "function":
            continue

        # Try nested format first (Chat Completions API)
        fn = t.get("function") if isinstance(t.get("function"), dict) else None
        if fn is not None:
            name = fn.get("name")
            desc = fn.get("description")
            params = fn.get("parameters")
        else:
            # Flat format (Responses API / Cursor style)
            name = t.get("name")
            desc = t.get("description")
            params = t.get("parameters")

        if not isinstance(name, str) or not name:
            continue
        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}

        out.append(
            {
                "type": "function",
                "name": name,
                "description": desc or "",
                "strict": False,
                "parameters": params,
            }
        )
    return out


def load_chatgpt_tokens(ensure_fresh: bool = True) -> tuple[str | None, str | None, str | None]:
    auth = read_auth_file()
    if not isinstance(auth, dict):
        return None, None, None

    tokens = auth.get("tokens") if isinstance(auth.get("tokens"), dict) else {}
    access_token: Optional[str] = tokens.get("access_token")
    account_id: Optional[str] = tokens.get("account_id")
    id_token: Optional[str] = tokens.get("id_token")
    refresh_token: Optional[str] = tokens.get("refresh_token")
    last_refresh = auth.get("last_refresh")

    if ensure_fresh and isinstance(refresh_token, str) and refresh_token and CLIENT_ID_DEFAULT:
        needs_refresh = _should_refresh_access_token(access_token, last_refresh)
        if needs_refresh or not (isinstance(access_token, str) and access_token):
            refreshed = _refresh_chatgpt_tokens(refresh_token, CLIENT_ID_DEFAULT)
            if refreshed:
                access_token = refreshed.get("access_token") or access_token
                id_token = refreshed.get("id_token") or id_token
                refresh_token = refreshed.get("refresh_token") or refresh_token
                account_id = refreshed.get("account_id") or account_id

                updated_tokens = dict(tokens)
                if isinstance(access_token, str) and access_token:
                    updated_tokens["access_token"] = access_token
                if isinstance(id_token, str) and id_token:
                    updated_tokens["id_token"] = id_token
                if isinstance(refresh_token, str) and refresh_token:
                    updated_tokens["refresh_token"] = refresh_token
                if isinstance(account_id, str) and account_id:
                    updated_tokens["account_id"] = account_id

                persisted = _persist_refreshed_auth(auth, updated_tokens)
                if persisted is not None:
                    auth, tokens = persisted
                else:
                    tokens = updated_tokens

    if not isinstance(account_id, str) or not account_id:
        account_id = _derive_account_id(id_token)

    access_token = access_token if isinstance(access_token, str) and access_token else None
    id_token = id_token if isinstance(id_token, str) and id_token else None
    account_id = account_id if isinstance(account_id, str) and account_id else None
    return access_token, account_id, id_token


def _should_refresh_access_token(access_token: Optional[str], last_refresh: Any) -> bool:
    if not isinstance(access_token, str) or not access_token:
        return True

    claims = parse_jwt_claims(access_token) or {}
    exp = claims.get("exp") if isinstance(claims, dict) else None
    now = datetime.datetime.now(datetime.timezone.utc)
    if isinstance(exp, (int, float)):
        try:
            expiry = datetime.datetime.fromtimestamp(float(exp), datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            expiry = None
        if expiry is not None:
            return expiry <= now + datetime.timedelta(minutes=5)

    if isinstance(last_refresh, str):
        refreshed_at = _parse_iso8601(last_refresh)
        if refreshed_at is not None:
            return refreshed_at <= now - datetime.timedelta(minutes=55)
    return False


def _refresh_chatgpt_tokens(refresh_token: str, client_id: str) -> Optional[Dict[str, Optional[str]]]:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "scope": "openid profile email offline_access",
    }

    try:
        resp = requests.post(OAUTH_TOKEN_URL, json=payload, timeout=30)
    except requests.RequestException as exc:
        eprint(f"ERROR: failed to refresh ChatGPT token: {exc}")
        return None

    if resp.status_code >= 400:
        eprint(f"ERROR: refresh token request returned status {resp.status_code}")
        return None

    try:
        data = resp.json()
    except ValueError as exc:
        eprint(f"ERROR: unable to parse refresh token response: {exc}")
        return None

    id_token = data.get("id_token")
    access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token") or refresh_token
    if not isinstance(id_token, str) or not isinstance(access_token, str):
        eprint("ERROR: refresh token response missing expected tokens")
        return None

    account_id = _derive_account_id(id_token)
    new_refresh_token = new_refresh_token if isinstance(new_refresh_token, str) and new_refresh_token else refresh_token
    return {
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "account_id": account_id,
    }


def _persist_refreshed_auth(auth: Dict[str, Any], updated_tokens: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    updated_auth = dict(auth)
    updated_auth["tokens"] = updated_tokens
    updated_auth["last_refresh"] = _now_iso8601()
    if write_auth_file(updated_auth):
        return updated_auth, updated_tokens
    eprint("ERROR: unable to persist refreshed auth tokens")
    return None


def _derive_account_id(id_token: Optional[str]) -> Optional[str]:
    if not isinstance(id_token, str) or not id_token:
        return None
    claims = parse_jwt_claims(id_token) or {}
    auth_claims = claims.get("https://api.openai.com/auth") if isinstance(claims, dict) else None
    if isinstance(auth_claims, dict):
        account_id = auth_claims.get("chatgpt_account_id")
        if isinstance(account_id, str) and account_id:
            return account_id
    return None


def _parse_iso8601(value: str) -> Optional[datetime.datetime]:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        return None


def _now_iso8601() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def get_effective_chatgpt_auth() -> tuple[str | None, str | None]:
    access_token, account_id, id_token = load_chatgpt_tokens()
    if not account_id:
        account_id = _derive_account_id(id_token)
    return access_token, account_id


def sse_translate_chat(
    upstream,
    model: str,
    created: int,
    verbose: bool = False,
    vlog=None,
    reasoning_compat: str = "think-tags",
    *,
    include_usage: bool = False,
):
    response_id = "chatcmpl-stream"
    compat = (reasoning_compat or "think-tags").strip().lower()
    think_open = False
    think_closed = False
    saw_output = False
    sent_stop_chunk = False
    saw_any_summary = False
    pending_summary_paragraph = False
    upstream_usage = None
    ws_state: dict[str, Any] = {}
    ws_index: dict[str, int] = {}
    ws_next_index: int = 0
    debug_stream = bool(os.getenv("CHATMOCK_DEBUG_STREAM"))
    _accumulated_text = []  # For debug logging
    
    def _serialize_tool_args(eff_args: Any, *, wrap_raw_strings: bool = True) -> str:
        """
        Serialize tool call arguments with proper JSON handling.

        Args:
            eff_args: Arguments to serialize (dict, list, str, or other)
            wrap_raw_strings: If False, return raw strings as-is (for custom tools)
                             If True, wrap non-JSON strings in {"query": ...} (for web_search)

        Returns:
            JSON string representation of the arguments, or raw string for custom tools
        """
        if isinstance(eff_args, (dict, list)):
            return json.dumps(eff_args)
        elif isinstance(eff_args, str):
            try:
                parsed = json.loads(eff_args)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed)
                else:
                    # Valid JSON but not dict/list - return raw if not wrapping
                    return eff_args if not wrap_raw_strings else json.dumps({"query": eff_args})
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON - return raw for custom tools, wrap for web_search
                return eff_args if not wrap_raw_strings else json.dumps({"query": eff_args})
        else:
            return "{}"
    
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
        try:
            line_iterator = upstream.iter_lines(decode_unicode=False)
        except requests.exceptions.ChunkedEncodingError as e:
            if verbose and vlog:
                vlog(f"Failed to start stream: {e}")
            yield b"data: [DONE]\n\n"
            return

        for raw in line_iterator:
            try:
                if not raw:
                    continue
                line = (
                    raw.decode("utf-8", errors="ignore")
                    if isinstance(raw, (bytes, bytearray))
                    else raw
                )
                if verbose and vlog:
                    vlog(line)
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
            except (
                requests.exceptions.ChunkedEncodingError,
                ConnectionError,
                BrokenPipeError,
            ) as e:
                # Connection interrupted mid-stream - end gracefully
                if verbose and vlog:
                    vlog(f"Stream interrupted: {e}")
                yield b"data: [DONE]\n\n"
                return
            kind = evt.get("type")
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id

            if isinstance(kind, str) and ("web_search_call" in kind):
                try:
                    call_id = evt.get("item_id") or "ws_call"
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS {kind} id={call_id} evt_keys={list(evt.keys())} -> tool_calls(web_search)")
                        except Exception:
                            pass
                    item = evt.get('item') if isinstance(evt.get('item'), dict) else {}
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS item={json.dumps(item, ensure_ascii=False)[:200]}")
                        except Exception:
                            pass
                    params_dict = ws_state.setdefault(call_id, {}) if isinstance(ws_state.get(call_id), dict) else {}
                    def _merge_from(src):
                        if not isinstance(src, dict):
                            return
                        # Level 1: Direct parameter containers
                        for whole in ('parameters','args','arguments','input','action'):
                            val = src.get(whole)
                            if isinstance(val, dict):
                                params_dict.update(val)
                            elif isinstance(val, str):
                                try:
                                    parsed = json.loads(val)
                                    if isinstance(parsed, dict):
                                        params_dict.update(parsed)
                                except (json.JSONDecodeError, ValueError, TypeError):
                                    pass
                        # Level 2: Nested structures like action.parameters
                        for container_key in ('action', 'call', 'invoke', 'request'):
                            container = src.get(container_key)
                            if isinstance(container, dict):
                                for param_key in ('parameters','args','arguments','input'):
                                    val = container.get(param_key)
                                    if isinstance(val, dict):
                                        params_dict.update(val)
                                    elif isinstance(val, str):
                                        try:
                                            parsed = json.loads(val)
                                            if isinstance(parsed, dict):
                                                params_dict.update(parsed)
                                        except (json.JSONDecodeError, ValueError, TypeError):
                                            pass
                        # Query field extraction with fallbacks
                        if isinstance(src.get('query'), str): 
                            params_dict.setdefault('query', src.get('query'))
                        if isinstance(src.get('q'), str): 
                            params_dict.setdefault('query', src.get('q'))
                        if isinstance(src.get('search_query'), str): 
                            params_dict.setdefault('query', src.get('search_query'))
                        if isinstance(src.get('search_input'), str): 
                            params_dict.setdefault('query', src.get('search_input'))
                        if isinstance(src.get('text'), str) and not params_dict.get('query'): 
                            params_dict['query'] = src.get('text')
                        # Check nested action for query
                        if isinstance(src.get('action'), dict):
                            action = src.get('action')
                            for qfield in ('query', 'q', 'search_query', 'search_input', 'text'):
                                if isinstance(action.get(qfield), str):
                                    params_dict.setdefault('query', action.get(qfield))
                        # Other parameters
                        for rk in ('recency','time_range','days'):
                            if src.get(rk) is not None and rk not in params_dict: params_dict[rk] = src.get(rk)
                        for dk in ('domains','include_domains','include'):
                            if isinstance(src.get(dk), list) and 'domains' not in params_dict: params_dict['domains'] = src.get(dk)
                        for mk in ('max_results','topn','limit'):
                            if src.get(mk) is not None and 'max_results' not in params_dict: params_dict['max_results'] = src.get(mk)
                    _merge_from(item)
                    _merge_from(evt if isinstance(evt, dict) else None)
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS after merge params_dict={params_dict}")
                        except Exception:
                            pass
                    params = params_dict if params_dict else None
                    if isinstance(params, dict):
                        try:
                            ws_state.setdefault(call_id, {}).update(params)
                        except Exception:
                            pass
                    eff_params = ws_state.get(call_id, params if isinstance(params, (dict, list, str)) else {})
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS eff_params={eff_params}")
                        except Exception:
                            pass
                    args_str = _serialize_tool_args(eff_params)
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS args_str={args_str}")
                        except Exception:
                            pass
                    if call_id not in ws_index:
                        ws_index[call_id] = ws_next_index
                        ws_next_index += 1
                    _idx = ws_index.get(call_id, 0)
                    delta_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": _idx,
                                            "id": call_id,
                                            "type": "function",
                                            "function": {"name": "web_search", "arguments": args_str},
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(delta_chunk)}\n\n".encode("utf-8")
                    if kind.endswith(".completed") or kind.endswith(".done"):
                        finish_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {}, "finish_reason": "tool_calls"}
                            ],
                        }
                        yield f"data: {json.dumps(finish_chunk)}\n\n".encode("utf-8")
                        sent_stop_chunk = True  # Prevent sending "stop" after "tool_calls"
                except Exception:
                    pass

            if kind == "response.output_text.delta":
                delta = evt.get("delta") or ""
                if debug_stream:
                    _accumulated_text.append(delta)
                if compat == "think-tags" and think_open and not think_closed:
                    close_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": "</think>"}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(close_chunk)}\n\n".encode("utf-8")
                    think_open = False
                    think_closed = True
                saw_output = True
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif kind == "response.output_item.done":
                item = evt.get("item") or {}
                if verbose and vlog and item.get("type") == "web_search_call":
                    try:
                        vlog(f"CM_TOOLS response.output_item.done web_search_call item={json.dumps(item, ensure_ascii=False)[:300]}")
                    except Exception:
                        pass
                item_type = item.get("type") if isinstance(item, dict) else None
                if item_type in ("function_call", "web_search_call", "custom_tool_call"):
                    call_id = item.get("call_id") or item.get("id") or ""
                    name = item.get("name") or ("web_search" if item_type == "web_search_call" else "")
                    # Debug: log raw item from ChatGPT to see exact response format
                    try:
                        import json as _json
                        raw_item_preview = _json.dumps(item, ensure_ascii=False)[:800]
                        print(f"[CHATMOCK] response.output_item.done: item_type={item_type!r} name={name!r}")
                        print(f"[CHATMOCK] RAW ITEM FROM CHATGPT: {raw_item_preview}")
                    except Exception:
                        pass

                    # Handle custom_tool_call: has raw 'input' string instead of JSON 'arguments'
                    # Per Responses API spec: https://platform.openai.com/docs/guides/tools#custom-tools
                    if item_type == "custom_tool_call":
                        raw_input = item.get("input") or ""
                        # Pass raw input directly as arguments (no JSON wrapping)
                        args = raw_input if isinstance(raw_input, str) else ""
                        if call_id not in ws_index:
                            ws_index[call_id] = ws_next_index
                            ws_next_index += 1
                        _idx = ws_index.get(call_id, 0)
                        if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                            # Stream tool call in OpenAI format: first chunk with id/name, then arguments in pieces
                            # This matches how OpenAI streams tool calls and may help Cursor track changes

                            # First chunk: tool call header with role (OpenAI format)
                            # OpenAI's first chunk includes role: "assistant" and content: null
                            header_chunk = {
                                "id": response_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "role": "assistant",
                                            "content": None,
                                            "tool_calls": [
                                                {
                                                    "index": _idx,
                                                    "id": call_id,
                                                    "type": "function",
                                                    "function": {"name": name, "arguments": ""},
                                                }
                                            ]
                                        },
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield f"data: {json.dumps(header_chunk)}\n\n".encode("utf-8")

                            # Stream arguments in chunks (OpenAI typically sends ~50-100 chars per chunk)
                            chunk_size = 100
                            for i in range(0, len(args), chunk_size):
                                args_piece = args[i:i + chunk_size]
                                args_chunk = {
                                    "id": response_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {
                                                "tool_calls": [
                                                    {
                                                        "index": _idx,
                                                        "function": {"arguments": args_piece},
                                                    }
                                                ]
                                            },
                                            "finish_reason": None,
                                        }
                                    ],
                                }
                                yield f"data: {json.dumps(args_chunk)}\n\n".encode("utf-8")

                            # Finish chunk with tool_calls reason
                            finish_chunk = {
                                "id": response_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                            }
                            yield f"data: {json.dumps(finish_chunk)}\n\n".encode("utf-8")
                            if debug_stream:
                                print(f"[STREAM] Sent finish_reason=tool_calls for custom_tool_call {name}")
                            # Log tool call for debugging
                            try:
                                args_preview = args[:500] if len(args) > 500 else args
                                print(f"[TOOL_CALL] {name} (custom): {args_preview}")
                            except Exception:
                                pass
                            sent_stop_chunk = True
                        continue  # Skip the function_call/web_search_call handling below

                    # Handle function_call and web_search_call
                    # Try to extract raw_args from multiple possible locations
                    raw_args = None
                    for key in ('arguments', 'parameters', 'input', 'action', 'query', 'q'):
                        if key in item:
                            raw_args = item.get(key)
                            break
                    if raw_args is None:
                        raw_args = {}
                    # Parse JSON strings
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                            if isinstance(parsed_args, dict):
                                raw_args = parsed_args
                        except (json.JSONDecodeError, ValueError, TypeError):
                            if item_type == "web_search_call":
                                raw_args = {"query": raw_args}
                    # For web_search_call, also check if action.parameters has the query
                    if item_type == "web_search_call" and isinstance(item.get("action"), dict):
                        action = item.get("action")
                        if isinstance(action.get("parameters"), dict):
                            if not isinstance(raw_args, dict):
                                raw_args = {}
                            raw_args.update(action.get("parameters"))
                        # Check for query in action fields
                        for qkey in ('query', 'q', 'search_query', 'search_input'):
                            if qkey in action and not (isinstance(raw_args, dict) and raw_args.get('query')):
                                if isinstance(raw_args, dict):
                                    raw_args.setdefault('query', action.get(qkey))
                                else:
                                    raw_args = {"query": action.get(qkey)}
                    if isinstance(raw_args, dict):
                        try:
                            ws_state.setdefault(call_id, {}).update(raw_args)
                        except Exception:
                            pass
                    eff_args = ws_state.get(call_id, raw_args if isinstance(raw_args, (dict, list, str)) else {})
                    if item_type == "web_search_call" and (not eff_args or (isinstance(eff_args, dict) and not eff_args.get('query'))):
                        eff_args = ws_state.get(call_id, {}) or {}
                    # Serialize arguments to JSON
                    # For web_search_call: wrap raw strings in {"query": ...}
                    # For function_call: pass raw strings as-is (may be custom tool with grammar)
                    try:
                        args = _serialize_tool_args(eff_args, wrap_raw_strings=(item_type == "web_search_call"))
                    except Exception:
                        args = "{}"
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS response.output_item.done raw_args={raw_args} eff_args={eff_args} args={args}")
                        except Exception:
                            pass
                    if item_type == "web_search_call" and verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS response.output_item.done web_search_call id={call_id} has_args={bool(args)}")
                        except Exception:
                            pass
                    if call_id not in ws_index:
                        ws_index[call_id] = ws_next_index
                        ws_next_index += 1
                    _idx = ws_index.get(call_id, 0)
                    if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
                        # Include role: assistant and content: null for OpenAI format compliance
                        delta_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [
                                            {
                                                "index": _idx,
                                                "id": call_id,
                                                "type": "function",
                                                "function": {"name": name, "arguments": args},
                                            }
                                        ]
                                    },
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(delta_chunk)}\n\n".encode("utf-8")

                        finish_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                        }
                        yield f"data: {json.dumps(finish_chunk)}\n\n".encode("utf-8")
                        if debug_stream:
                            print(f"[STREAM] Sent finish_reason=tool_calls for {name}")
                        # Always log tool call arguments (useful for debugging)
                        try:
                            args_preview = args[:500] if len(args) > 500 else args
                            print(f"[TOOL_CALL] {name}: {args_preview}")
                        except Exception:
                            pass
                        sent_stop_chunk = True  # Prevent sending "stop" after "tool_calls"
            elif kind == "response.reasoning_summary_part.added":
                if compat in ("think-tags", "o3"):
                    if saw_any_summary:
                        pending_summary_paragraph = True
                    else:
                        saw_any_summary = True
            elif kind in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                delta_txt = evt.get("delta") or ""
                if compat == "o3":
                    if kind == "response.reasoning_summary_text.delta" and pending_summary_paragraph:
                        nl_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"reasoning": {"content": [{"type": "text", "text": "\n"}]}},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(nl_chunk)}\n\n".encode("utf-8")
                        pending_summary_paragraph = False
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"reasoning": {"content": [{"type": "text", "text": delta_txt}]}},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                elif compat == "think-tags":
                    if not think_open and not think_closed:
                        open_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": "<think>"}, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(open_chunk)}\n\n".encode("utf-8")
                        think_open = True
                    if think_open and not think_closed:
                        if kind == "response.reasoning_summary_text.delta" and pending_summary_paragraph:
                            nl_chunk = {
                                "id": response_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [{"index": 0, "delta": {"content": "\n"}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(nl_chunk)}\n\n".encode("utf-8")
                            pending_summary_paragraph = False
                        content_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": delta_txt}, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(content_chunk)}\n\n".encode("utf-8")
                else:
                    if kind == "response.reasoning_summary_text.delta":
                        chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"reasoning_summary": delta_txt, "reasoning": delta_txt},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                    else:
                        chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {"reasoning": delta_txt}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif isinstance(kind, str) and kind.endswith(".done"):
                pass
            elif kind == "response.output_text.done":
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                if debug_stream:
                    print(f"[STREAM] Sent finish_reason=stop (output_text.done)")
                sent_stop_chunk = True
            elif kind == "response.failed":
                err = evt.get("response", {}).get("error", {}).get("message", "response.failed")
                chunk = {"error": {"message": err}}
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif kind == "response.completed":
                if debug_stream:
                    print(f"[STREAM] response.completed received, sent_stop_chunk={sent_stop_chunk}")
                    if _accumulated_text and not sent_stop_chunk:
                        text_preview = "".join(_accumulated_text)[:500]
                        print(f"[STREAM] Model text output (no tools): {text_preview!r}")
                m = _extract_usage(evt)
                if m:
                    upstream_usage = m
                if compat == "think-tags" and think_open and not think_closed:
                    close_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {"content": "</think>"}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(close_chunk)}\n\n".encode("utf-8")
                    think_open = False
                    think_closed = True
                if not sent_stop_chunk:
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                    if debug_stream:
                        print(f"[STREAM] Sent finish_reason=stop (response.completed, no prior stop)")
                    sent_stop_chunk = True
                elif debug_stream:
                    print(f"[STREAM] Skipped stop (already sent_stop_chunk=True)")

                if include_usage and upstream_usage:
                    try:
                        usage_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                            "usage": upstream_usage,
                        }
                        yield f"data: {json.dumps(usage_chunk)}\n\n".encode("utf-8")
                    except Exception:
                        pass
                yield b"data: [DONE]\n\n"
                break
    finally:
        upstream.close()


def sse_translate_text(upstream, model: str, created: int, verbose: bool = False, vlog=None, *, include_usage: bool = False):
    response_id = "cmpl-stream"
    upstream_usage = None
    
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
            if verbose and vlog:
                vlog(line)
            if not line.startswith("data: "):
                continue
            data = line[len("data: "):].strip()
            if not data or data == "[DONE]":
                if data == "[DONE]":
                    chunk = {
                        "id": response_id,
                        "object": "text_completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                continue
            try:
                evt = json.loads(data)
            except Exception:
                continue
            kind = evt.get("type")
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id
            if kind == "response.output_text.delta":
                delta_text = evt.get("delta") or ""
                chunk = {
                    "id": response_id,
                    "object": "text_completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "text": delta_text, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif kind == "response.output_text.done":
                chunk = {
                    "id": response_id,
                    "object": "text_completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif kind == "response.completed":
                m = _extract_usage(evt)
                if m:
                    upstream_usage = m
                if include_usage and upstream_usage:
                    try:
                        usage_chunk = {
                            "id": response_id,
                            "object": "text_completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "text": "", "finish_reason": None}],
                            "usage": upstream_usage,
                        }
                        yield f"data: {json.dumps(usage_chunk)}\n\n".encode("utf-8")
                    except Exception:
                        pass
                yield b"data: [DONE]\n\n"
                break
    finally:
        upstream.close()
