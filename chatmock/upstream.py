from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from flask import Response, current_app, jsonify, make_response

from .config import CHATGPT_RESPONSES_URL, ORIGINATOR
from .http import build_cors_headers
from .model_registry import normalize_model_name
from .session import ensure_session_id
from flask import request as flask_request
from .utils import get_codex_user_agent, get_effective_chatgpt_auth, resolve_installation_id


def _log_json(prefix: str, payload: Any) -> None:
    try:
        print(f"{prefix}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    except Exception:
        try:
            print(f"{prefix}\n{payload}")
        except Exception:
            pass

def start_upstream_request(
    model: str,
    input_items: List[Dict[str, Any]],
    *,
    instructions: str | None = None,
    tools: List[Dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool = False,
    reasoning_param: Dict[str, Any] | None = None,
    service_tier: str | None = None,
):
    access_token, account_id = get_effective_chatgpt_auth()
    if not access_token or not account_id:
        resp = make_response(
            jsonify(
                {
                    "error": {
                        "message": "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first.",
                    }
                }
            ),
            401,
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    include: List[str] = []
    if isinstance(reasoning_param, dict):
        include.append("reasoning.encrypted_content")

    client_session_id = None
    try:
        client_session_id = (
            flask_request.headers.get("X-Session-Id")
            or flask_request.headers.get("session_id")
            or None
        )
    except Exception:
        client_session_id = None
    session_id = ensure_session_id(instructions, input_items, client_session_id)

    responses_payload = {
        "model": model,
        "input": input_items,
        "tools": tools or [],
        "tool_choice": tool_choice if tool_choice in ("auto", "none") or isinstance(tool_choice, dict) else "auto",
        "parallel_tool_calls": bool(parallel_tool_calls),
        "store": False,
        "stream": True,
        "prompt_cache_key": session_id,
    }
    if instructions is not None:
        responses_payload["instructions"] = instructions
    if include:
        responses_payload["include"] = include

    if reasoning_param is not None:
        responses_payload["reasoning"] = reasoning_param
    if isinstance(service_tier, str) and service_tier.strip():
        responses_payload["service_tier"] = service_tier.strip().lower()

    return start_upstream_raw_request(
        responses_payload,
        session_id=session_id,
        stream=True,
    )


def build_upstream_headers(
    access_token: str,
    account_id: str,
    session_id: str,
    *,
    accept: str = "text/event-stream",
) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": accept,
        "ChatGPT-Account-ID": account_id,
        "User-Agent": get_codex_user_agent(),
        "originator": ORIGINATOR,
        "OpenAI-Beta": "responses=experimental",
        "session-id": session_id,
        "x-codex-installation-id": resolve_installation_id(),
    }


def start_upstream_raw_request(
    responses_payload: Dict[str, Any],
    *,
    session_id: str | None = None,
    stream: bool = True,
):
    access_token, account_id = get_effective_chatgpt_auth()
    if not access_token or not account_id:
        resp = make_response(
            jsonify(
                {
                    "error": {
                        "message": "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first.",
                    }
                }
            ),
            401,
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    effective_session_id = session_id
    if not isinstance(effective_session_id, str) or not effective_session_id.strip():
        payload_prompt_cache_key = responses_payload.get("prompt_cache_key")
        if isinstance(payload_prompt_cache_key, str) and payload_prompt_cache_key.strip():
            effective_session_id = payload_prompt_cache_key.strip()
    if not isinstance(effective_session_id, str) or not effective_session_id.strip():
        effective_session_id = str(int(time.time() * 1000))

    verbose = False
    try:
        verbose = bool(current_app.config.get("VERBOSE"))
    except Exception:
        verbose = False
    if verbose:
        _log_json("OUTBOUND >> ChatGPT Responses API payload", responses_payload)

    payload_to_send = dict(responses_payload)
    client_metadata = payload_to_send.get("client_metadata")
    if not isinstance(client_metadata, dict):
        client_metadata = {}
    else:
        client_metadata = dict(client_metadata)
    client_metadata.setdefault("x-codex-installation-id", resolve_installation_id())
    payload_to_send["client_metadata"] = client_metadata

    headers = build_upstream_headers(
        access_token,
        account_id,
        effective_session_id,
        accept=("text/event-stream" if stream else "application/json"),
    )

    try:
        upstream = requests.post(
            CHATGPT_RESPONSES_URL,
            headers=headers,
            json=payload_to_send,
            stream=stream,
            timeout=600,
        )
    except requests.RequestException as e:
        resp = make_response(jsonify({"error": {"message": f"Upstream ChatGPT request failed: {e}"}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    if upstream.status_code == 401:
        refreshed_access_token, refreshed_account_id = get_effective_chatgpt_auth(force_refresh=True)
        if (
            isinstance(refreshed_access_token, str)
            and refreshed_access_token
            and isinstance(refreshed_account_id, str)
            and refreshed_account_id
            and refreshed_access_token != access_token
        ):
            try:
                upstream.close()
            except Exception:
                pass
            retry_headers = build_upstream_headers(
                refreshed_access_token,
                refreshed_account_id,
                effective_session_id,
                accept=("text/event-stream" if stream else "application/json"),
            )
            try:
                upstream = requests.post(
                    CHATGPT_RESPONSES_URL,
                    headers=retry_headers,
                    json=payload_to_send,
                    stream=stream,
                    timeout=600,
                )
            except requests.RequestException as e:
                resp = make_response(jsonify({"error": {"message": f"Upstream ChatGPT request failed after token refresh: {e}"}}), 502)
                for k, v in build_cors_headers().items():
                    resp.headers.setdefault(k, v)
                return None, resp
    return upstream, None


def build_upstream_websocket_url() -> str:
    parsed = urlparse(CHATGPT_RESPONSES_URL)
    scheme = parsed.scheme.lower()
    if scheme == "https":
        parsed = parsed._replace(scheme="wss")
    elif scheme == "http":
        parsed = parsed._replace(scheme="ws")
    return urlunparse(parsed)
