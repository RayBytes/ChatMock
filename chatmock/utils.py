"""Utility helpers for auth, payload transforms, and SSE translation."""

from __future__ import annotations

import base64
import binascii
import contextlib
import datetime
import hashlib
import json
import os
import secrets
import sys
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import requests

from .config import CLIENT_ID_DEFAULT, OAUTH_TOKEN_URL
from .models import PkceCodes

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


def eprint(*args: object) -> None:
    """Write to stderr without using print (avoids Ruff T201)."""
    msg = " ".join(str(a) for a in args)
    with contextlib.suppress(Exception):
        sys.stderr.write(msg + "\n")


def get_home_dir() -> str:
    """Return the directory used to persist ChatMock auth files."""
    home_env = os.getenv("CHATGPT_LOCAL_HOME") or os.getenv("CODEX_HOME")
    if home_env:
        return str(Path(home_env))
    return str(Path("~/.chatgpt-local").expanduser())


def read_auth_file() -> dict[str, Any] | None:
    """Load persisted auth from common locations, if present."""
    for base in [
        os.getenv("CHATGPT_LOCAL_HOME"),
        os.getenv("CODEX_HOME"),
        str(Path("~/.chatgpt-local").expanduser()),
        str(Path("~/.codex").expanduser()),
    ]:
        if not base:
            continue
        path = Path(base) / "auth.json"
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError):
            continue
        else:
            return data
    return None


def write_auth_file(auth: dict[str, Any]) -> bool:
    """Persist the auth bundle to the default location."""
    home = Path(get_home_dir())
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        eprint(f"ERROR: unable to create auth home directory {home}: {exc}")
        return False
    path = home / "auth.json"
    try:
        with path.open("w", encoding="utf-8") as fp:
            with contextlib.suppress(AttributeError, OSError):
                os.fchmod(fp.fileno(), 0o600)  # type: ignore[attr-defined]
            json.dump(auth, fp, indent=2)
    except (OSError, TypeError, ValueError) as exc:
        eprint(f"ERROR: unable to write auth file: {exc}")
        return False
    else:
        return True


EXPECTED_JWT_PARTS = 2


def parse_jwt_claims(token: str) -> dict[str, Any] | None:
    """Decode a JWT and return its claims dictionary, if valid."""
    if not token or token.count(".") != EXPECTED_JWT_PARTS:
        return None
    try:
        _, payload, _ = token.split(".")
        padded = payload + "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(padded.encode())
        decoded = json.loads(data.decode())
    except (ValueError, json.JSONDecodeError, binascii.Error, UnicodeDecodeError):
        return None
    else:
        return decoded


def generate_pkce() -> PkceCodes:
    """Generate PKCE verifier/challenge pair."""
    code_verifier = secrets.token_hex(64)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return PkceCodes(code_verifier=code_verifier, code_challenge=code_challenge)


def convert_chat_messages_to_responses_input(  # noqa: C901, PLR0912, PLR0915
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Translate OpenAI chat message objects into Responses API input items."""

    def _normalize_image_data_url(url: str) -> str:
        try:
            if not url.startswith("data:image/"):
                return url
            if ";base64," not in url:
                return url
            header, data = url.split(",", 1)
            with contextlib.suppress(Exception):
                data = unquote(data)
            data = data.strip().replace("\n", "").replace("\r", "")
            data = data.replace("-", "+").replace("_", "/")
            pad = (-len(data)) % 4
            if pad:
                data = data + ("=" * pad)
            # Validate base64 payload; errors are acceptable — we still return the sanitized url
            base64.b64decode(data, validate=True)
        except (ValueError, TypeError, binascii.Error, UnicodeDecodeError):
            # Even if validation fails, return the sanitized/padded data URL
            return f"{header},{data}" if ("header" in locals() and "data" in locals()) else url
        else:
            return f"{header},{data}"

    input_items: list[dict[str, Any]] = []
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
        content_items: list[dict[str, Any]] = []
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
                        content_items.append(
                            {"type": "input_image", "image_url": _normalize_image_data_url(url)}
                        )
        elif isinstance(content, str) and content:
            kind = "output_text" if role == "assistant" else "input_text"
            content_items.append({"type": kind, "text": content})

        if not content_items:
            continue
        role_out = "assistant" if role == "assistant" else "user"
        input_items.append({"type": "message", "role": role_out, "content": content_items})
    return input_items


def convert_tools_chat_to_responses(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize OpenAI Chat tool specs into Responses API tool objects."""
    out: list[dict[str, Any]] = []
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


def load_chatgpt_tokens(ensure_fresh: bool = True) -> tuple[str | None, str | None, str | None]:  # noqa: C901, FBT001, FBT002
    """Load tokens from disk, optionally refreshing access token."""
    auth = read_auth_file()
    if not isinstance(auth, dict):
        return None, None, None

    tokens = auth.get("tokens") if isinstance(auth.get("tokens"), dict) else {}
    access_token: str | None = tokens.get("access_token")
    account_id: str | None = tokens.get("account_id")
    id_token: str | None = tokens.get("id_token")
    refresh_token: str | None = tokens.get("refresh_token")
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


def _should_refresh_access_token(access_token: str | None, last_refresh: object) -> bool:
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


def _refresh_chatgpt_tokens(refresh_token: str, client_id: str) -> dict[str, str | None] | None:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "scope": "openid profile email",
    }

    try:
        resp = requests.post(OAUTH_TOKEN_URL, json=payload, timeout=30)
    except requests.RequestException as exc:
        eprint(f"ERROR: failed to refresh ChatGPT token: {exc}")
        return None

    if resp.status_code >= HTTPStatus.BAD_REQUEST:
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
    new_refresh_token = (
        new_refresh_token
        if isinstance(new_refresh_token, str) and new_refresh_token
        else refresh_token
    )
    return {
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "account_id": account_id,
    }


def _persist_refreshed_auth(
    auth: dict[str, Any], updated_tokens: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    updated_auth = dict(auth)
    updated_auth["tokens"] = updated_tokens
    updated_auth["last_refresh"] = _now_iso8601()
    if write_auth_file(updated_auth):
        return updated_auth, updated_tokens
    eprint("ERROR: unable to persist refreshed auth tokens")
    return None


def _derive_account_id(id_token: str | None) -> str | None:
    if not isinstance(id_token, str) or not id_token:
        return None
    claims = parse_jwt_claims(id_token) or {}
    auth_claims = claims.get("https://api.openai.com/auth") if isinstance(claims, dict) else None
    if isinstance(auth_claims, dict):
        account_id = auth_claims.get("chatgpt_account_id")
        if isinstance(account_id, str) and account_id:
            return account_id
    return None


def _parse_iso8601(value: str) -> datetime.datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def _now_iso8601() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def get_effective_chatgpt_auth() -> tuple[str | None, str | None]:
    """Return (access_token, account_id) using ID token when necessary."""
    access_token, account_id, id_token = load_chatgpt_tokens()
    if not account_id:
        account_id = _derive_account_id(id_token)
    return access_token, account_id


def sse_translate_chat(  # noqa: C901, PLR0913, PLR0912, PLR0915
    upstream: object,
    model: str,
    created: int,
    *,
    verbose: bool = False,
    vlog: Callable[[str], None] | None = None,
    reasoning_compat: str = "think-tags",
    include_usage: bool = False,
) -> Iterator[bytes]:
    """Stream SSE from Responses API and translate to OpenAI chat chunks."""
    response_id = "chatcmpl-stream"
    compat = (reasoning_compat or "think-tags").strip().lower()
    think_open = False
    think_closed = False
    saw_any_summary = False
    pending_summary_paragraph = False
    upstream_usage = None
    ws_state: dict[str, Any] = {}
    ws_index: dict[str, int] = {}
    ws_next_index: int = 0

    def _serialize_tool_args(eff_args: object) -> str:
        """Serialize tool call arguments with proper JSON handling."""
        if isinstance(eff_args, (dict, list)):
            return json.dumps(eff_args)
        if isinstance(eff_args, str):
            try:
                parsed = json.loads(eff_args)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed)
                return json.dumps({"query": eff_args})
            except (json.JSONDecodeError, ValueError):
                return json.dumps({"query": eff_args})
        else:
            return "{}"

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
            kind = evt.get("type")
            if isinstance(evt.get("response"), dict) and isinstance(evt["response"].get("id"), str):
                response_id = evt["response"].get("id") or response_id

            if isinstance(kind, str) and ("web_search_call" in kind):
                try:
                    call_id = evt.get("item_id") or "ws_call"
                    if verbose and vlog:
                        with contextlib.suppress(Exception):
                            vlog(f"CM_TOOLS {kind} id={call_id} -> tool_calls(web_search)")
                    item = evt.get("item") if isinstance(evt.get("item"), dict) else {}
                    params_dict = (
                        ws_state.setdefault(call_id, {})
                        if isinstance(ws_state.get(call_id), dict)
                        else {}
                    )

                    def _merge_from(  # noqa: C901
                        src: dict[str, Any] | None, _params: dict[str, Any] = params_dict
                    ) -> None:
                        # src is always a dict in this flow; operate directly
                        for whole in ("parameters", "args", "arguments", "input"):
                            if isinstance(src.get(whole), dict):  # type: ignore[union-attr]
                                _params.update(src.get(whole))  # type: ignore[union-attr]
                        if isinstance(src.get("query"), str):  # type: ignore[union-attr]
                            _params.setdefault("query", src.get("query"))  # type: ignore[union-attr]
                        if isinstance(src.get("q"), str):  # type: ignore[union-attr]
                            _params.setdefault("query", src.get("q"))  # type: ignore[union-attr]
                        for rk in ("recency", "time_range", "days"):
                            if src.get(rk) is not None and rk not in _params:  # type: ignore[union-attr]
                                _params[rk] = src.get(rk)  # type: ignore[union-attr]
                        for dk in ("domains", "include_domains", "include"):
                            if isinstance(src.get(dk), list) and "domains" not in _params:  # type: ignore[union-attr]
                                _params["domains"] = src.get(dk)  # type: ignore[union-attr]
                        for mk in ("max_results", "topn", "limit"):
                            if src.get(mk) is not None and "max_results" not in _params:  # type: ignore[union-attr]
                                _params["max_results"] = src.get(mk)  # type: ignore[union-attr]

                    _merge_from(item)
                    _merge_from(evt if isinstance(evt, dict) else None)
                    params = params_dict if params_dict else None
                    if isinstance(params, dict):
                        with contextlib.suppress(Exception):
                            ws_state.setdefault(call_id, {}).update(params)
                    eff_params = ws_state.get(
                        call_id,
                        params if isinstance(params, (dict, list, str)) else {},
                    )
                    args_str = _serialize_tool_args(eff_params)
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
                                            "function": {
                                                "name": "web_search",
                                                "arguments": args_str,
                                            },
                                        }
                                    ]
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(delta_chunk)}\n\n".encode()
                    if kind.endswith((".completed", ".done")):
                        finish_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
                        }
                        yield f"data: {json.dumps(finish_chunk)}\n\n".encode()
                except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    pass

            if kind == "response.output_text.delta":
                delta = evt.get("delta") or ""
                if compat == "think-tags" and think_open and not think_closed:
                    close_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": "</think>"}, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(close_chunk)}\n\n".encode()
                    think_open = False
                    think_closed = True
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            elif kind == "response.output_item.done":
                item = evt.get("item") or {}
                if isinstance(item, dict) and (
                    item.get("type") == "function_call" or item.get("type") == "web_search_call"
                ):
                    call_id = item.get("call_id") or item.get("id") or ""
                    name = item.get("name") or (
                        "web_search" if item.get("type") == "web_search_call" else ""
                    )
                    raw_args = item.get("arguments") or item.get("parameters")
                    if isinstance(raw_args, dict):
                        with contextlib.suppress(Exception):
                            ws_state.setdefault(call_id, {}).update(raw_args)
                    eff_args = ws_state.get(
                        call_id, raw_args if isinstance(raw_args, (dict, list, str)) else {}
                    )
                    args = _serialize_tool_args(eff_args)
                    if item.get("type") == "web_search_call" and verbose and vlog:
                        with contextlib.suppress(Exception):
                            vlog(
                                "CM_TOOLS response.output_item.done web_search_call "
                                f"id={call_id} has_args={bool(args)}"
                            )
                    _idx = ws_index.setdefault(call_id, ws_next_index)
                    ws_next_index += 1
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
                                    # Mark the tool call completion on the same chunk
                                    "finish_reason": "tool_calls",
                                }
                            ],
                        }
                        yield f"data: {json.dumps(delta_chunk)}\n\n".encode()
            elif kind == "response.reasoning_summary_part.added":
                if compat in ("think-tags", "o3"):
                    if saw_any_summary:
                        pending_summary_paragraph = True
                    else:
                        saw_any_summary = True
            elif kind in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                delta_txt = evt.get("delta") or ""
                if compat == "o3":
                    if (
                        kind == "response.reasoning_summary_text.delta"
                        and pending_summary_paragraph
                    ):
                        nl_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "reasoning": {"content": [{"type": "text", "text": "\n"}]}
                                    },
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(nl_chunk)}\n\n".encode()
                        pending_summary_paragraph = False
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "reasoning": {"content": [{"type": "text", "text": delta_txt}]}
                                },
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n".encode()
                elif compat == "think-tags":
                    if not think_open and not think_closed:
                        open_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {"content": "<think>"}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(open_chunk)}\n\n".encode()
                        think_open = True
                    if think_open and not think_closed:
                        if (
                            kind == "response.reasoning_summary_text.delta"
                            and pending_summary_paragraph
                        ):
                            nl_chunk = {
                                "id": response_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [
                                    {"index": 0, "delta": {"content": "\n"}, "finish_reason": None}
                                ],
                            }
                            yield f"data: {json.dumps(nl_chunk)}\n\n".encode()
                            pending_summary_paragraph = False
                        content_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {"index": 0, "delta": {"content": delta_txt}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(content_chunk)}\n\n".encode()
                elif kind == "response.reasoning_summary_text.delta":
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
                    yield f"data: {json.dumps(chunk)}\n\n".encode()
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
                    yield f"data: {json.dumps(chunk)}\n\n".encode()
            elif isinstance(kind, str) and kind.endswith(".done"):
                # Ignore generic done markers
                continue
            # Note: output_text.done is treated as a generic .done (no-op) above.
            elif kind == "response.failed":
                err = evt.get("response", {}).get("error", {}).get("message", "response.failed")
                chunk = {"error": {"message": err}}
                yield f"data: {json.dumps(chunk)}\n\n".encode()
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
                        "choices": [
                            {"index": 0, "delta": {"content": "</think>"}, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(close_chunk)}\n\n".encode()
                    think_open = False
                    think_closed = True
                if include_usage and upstream_usage:
                    with contextlib.suppress(Exception):
                        usage_chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                            "usage": upstream_usage,
                        }
                        yield f"data: {json.dumps(usage_chunk)}\n\n".encode()
                yield b"data: [DONE]\n\n"
                break
    finally:
        upstream.close()


def sse_translate_text(  # noqa: C901, PLR0912, PLR0915, PLR0913
    upstream: object,
    model: str,
    created: int,
    *,
    verbose: bool = False,
    vlog: Callable[[str], None] | None = None,
    include_usage: bool = False,
) -> Iterator[bytes]:
    """Stream SSE from Responses API and translate to OpenAI text chunks."""
    response_id = "cmpl-stream"
    upstream_usage = None

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
            if verbose and vlog:
                vlog(line)
            if not line.startswith("data: "):
                continue
            data = line[len("data: ") :].strip()
            if not data:
                continue
            if data == "[DONE]":
                chunk = {
                    "id": response_id,
                    "object": "text_completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
                continue
            try:
                evt = json.loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
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
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            elif kind == "response.output_text.done":
                chunk = {
                    "id": response_id,
                    "object": "text_completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            elif kind == "response.completed":
                m = _extract_usage(evt)
                if m:
                    upstream_usage = m
                if include_usage and upstream_usage:
                    with contextlib.suppress(Exception):
                        usage_chunk = {
                            "id": response_id,
                            "object": "text_completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "text": "", "finish_reason": None}],
                            "usage": upstream_usage,
                        }
                        yield f"data: {json.dumps(usage_chunk)}\n\n".encode()
                yield b"data: [DONE]\n\n"
                return
    finally:
        upstream.close()
