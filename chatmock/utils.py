from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sys
from typing import Any, Dict, List


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
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue

        if role == "tool":
            call_id = message.get("tool_call_id") or message.get("id")
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
        input_items.append({"type": "message", "role": role_out, "content": content_items})
    return input_items


def convert_tools_chat_to_responses(tools: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(tools, list):
        return out
    for t in tools:
        if not isinstance(t, dict):
            continue
        if t.get("type") != "function":
            continue
        fn = t.get("function") if isinstance(t.get("function"), dict) else {}
        name = fn.get("name") if isinstance(fn, dict) else None
        if not isinstance(name, str) or not name:
            continue
        desc = fn.get("description") if isinstance(fn, dict) else None
        params = fn.get("parameters") if isinstance(fn, dict) else None
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


def load_chatgpt_tokens() -> tuple[str | None, str | None, str | None]:
    auth = read_auth_file()
    if not auth:
        return None, None, None
    tokens = auth.get("tokens", {}) if isinstance(auth, dict) else {}
    return tokens.get("access_token"), tokens.get("account_id"), tokens.get("id_token")


def get_effective_chatgpt_auth() -> tuple[str | None, str | None]:
    access_token, account_id, id_token = load_chatgpt_tokens()
    if not account_id and id_token:
        claims = parse_jwt_claims(id_token) or {}
        auth_claims = claims.get("https://api.openai.com/auth", {}) or {}
        if isinstance(auth_claims, dict):
            account_id = auth_claims.get("chatgpt_account_id")
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
    saw_any_summary = False
    pending_summary_paragraph = False
    upstream_usage = None
    ws_state: dict[str, Any] = {}
    ws_index: dict[str, int] = {}
    ws_next_index: int = 0
    
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
            if verbose and vlog:
                vlog(line)
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
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id

            if isinstance(kind, str) and ("web_search_call" in kind):
                try:
                    call_id = evt.get("item_id") or "ws_call"
                    if verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS {kind} id={call_id} -> tool_calls(web_search)")
                        except Exception:
                            pass
                    item = evt.get('item') if isinstance(evt.get('item'), dict) else {}
                    params_dict = ws_state.setdefault(call_id, {}) if isinstance(ws_state.get(call_id), dict) else {}
                    def _merge_from(src):
                        if not isinstance(src, dict):
                            return
                        for whole in ('parameters','args','arguments','input'):
                            if isinstance(src.get(whole), dict):
                                params_dict.update(src.get(whole))
                        if isinstance(src.get('query'), str): params_dict.setdefault('query', src.get('query'))
                        if isinstance(src.get('q'), str): params_dict.setdefault('query', src.get('q'))
                        for rk in ('recency','time_range','days'):
                            if src.get(rk) is not None and rk not in params_dict: params_dict[rk] = src.get(rk)
                        for dk in ('domains','include_domains','include'):
                            if isinstance(src.get(dk), list) and 'domains' not in params_dict: params_dict['domains'] = src.get(dk)
                        for mk in ('max_results','topn','limit'):
                            if src.get(mk) is not None and 'max_results' not in params_dict: params_dict['max_results'] = src.get(mk)
                    _merge_from(item)
                    _merge_from(evt if isinstance(evt, dict) else None)
                    params = params_dict if params_dict else None
                    if isinstance(params, dict):
                        try:
                            ws_state.setdefault(call_id, {}).update(params)
                        except Exception:
                            pass
                    eff_params = ws_state.get(call_id, params if isinstance(params, (dict, list, str)) else {})
                    if isinstance(eff_params, (dict, list)):
                        args_str = json.dumps(eff_params)
                    elif isinstance(eff_params, str):
                        args_str = json.dumps({"query": eff_params})
                    else:
                        args_str = "{}"
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
                except Exception:
                    pass

            if kind == "response.output_text.delta":
                delta = evt.get("delta") or ""
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
                if isinstance(item, dict) and (item.get("type") == "function_call" or item.get("type") == "web_search_call"):
                    call_id = item.get("call_id") or item.get("id") or ""
                    name = item.get("name") or ("web_search" if item.get("type") == "web_search_call" else "")
                    raw_args = item.get("arguments") or item.get("parameters")
                    if isinstance(raw_args, dict):
                        try:
                            ws_state.setdefault(call_id, {}).update(raw_args)
                        except Exception:
                            pass
                    eff_args = ws_state.get(call_id, raw_args if isinstance(raw_args, (dict, list, str)) else {})
                    try:
                        if isinstance(eff_args, (dict, list)):
                            args = json.dumps(eff_args)
                        elif isinstance(eff_args, str):
                            args = json.dumps({"query": eff_args})
                        else:
                            args = "{}"
                    except Exception:
                        args = "{}"
                    if item.get("type") == "web_search_call" and verbose and vlog:
                        try:
                            vlog(f"CM_TOOLS response.output_item.done web_search_call id={call_id} has_args={bool(args)}")
                        except Exception:
                            pass
                    if call_id not in ws_index:
                        ws_index[call_id] = ws_next_index
                        ws_next_index += 1
                    _idx = ws_index.get(call_id, 0)
                    if isinstance(call_id, str) and isinstance(name, str) and isinstance(args, str):
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
            elif kind == "response.failed":
                err = evt.get("response", {}).get("error", {}).get("message", "response.failed")
                chunk = {"error": {"message": err}}
                yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
            elif kind == "response.completed":
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

