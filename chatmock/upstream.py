from __future__ import annotations

import json
import requests
from typing import Any, Dict, List, Optional
from flask import Response, jsonify, make_response, request as flask_request

from .config import (
    CHATGPT_RESPONSES_URL,
    BASE_INSTRUCTIONS,
)
from .http import build_cors_headers
from .session import ensure_session_id
from .utils import get_effective_chatgpt_auth

def normalize_model_name(name: str | None, debug_model: str | None = None) -> str:
    """Only allow the two supported models."""
    allowed = ("codex-mini-latest", "gpt-5")
    selected = (
        debug_model.strip()
        if isinstance(debug_model, str) and debug_model.strip()
        else (name or "").strip()
    )
    if selected not in allowed:
        raise ValueError(f"Unsupported model: {selected}")
    return selected

def start_upstream_request(
    model: str,
    input_items: List[Dict[str, Any]],
    *,
    instructions: str | None = None,
    tools: List[Dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    parallel_tool_calls: bool = False,
    reasoning_param: Dict[str, Any] | None = None,
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

    try:
        client_session_id = (
            flask_request.headers.get("X-Session-Id")
            or flask_request.headers.get("session_id")
            or None
        )
    except Exception:
        client_session_id = None
    session_id = ensure_session_id(instructions, input_items, client_session_id)

    payload: Dict[str, Any] = {
        "model": model,
        "instructions": instructions if isinstance(instructions, str) and instructions.strip() else instructions,
        "input": input_items,
        "tools": tools or [],
        "tool_choice": tool_choice if tool_choice in ("auto", "none") or isinstance(tool_choice, dict) else "auto",
        "parallel_tool_calls": bool(parallel_tool_calls),
        "store": False,
        "stream": True,
        "prompt_cache_key": session_id,
    }
    if isinstance(reasoning_param, dict):
        payload["include"] = ["reasoning.encrypted_content"]
        payload["reasoning"] = reasoning_param

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "chatgpt-account-id": account_id,
        "OpenAI-Beta": "responses=experimental",
        "session_id": session_id,
    }

    try:
        upstream = requests.post(
            CHATGPT_RESPONSES_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=600,
        )
    except requests.RequestException as e:
        resp = make_response(jsonify({"error": {"message": f"Upstream ChatGPT request failed: {e}"}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    return upstream, None

def list_advertised_models(force_refresh: bool = False) -> List[str]:
    """Return only the two supported models."""
    return ["codex-mini-latest", "gpt-5"]
