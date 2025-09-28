"""Upstream request helpers to the ChatGPT Responses API."""

from __future__ import annotations

from typing import Any

import requests
from flask import Response, jsonify, make_response
from flask import request as flask_request

from . import utils as utils_mod
from .config import CHATGPT_RESPONSES_URL
from .http import build_cors_headers
from .session import ensure_session_id


def normalize_model_name(name: str | None, debug_model: str | None = None) -> str:
    """Map aliases and effort-suffixed model names to a canonical base."""
    if isinstance(debug_model, str) and debug_model.strip():
        return debug_model.strip()
    if not isinstance(name, str) or not name.strip():
        return "gpt-5"
    base = name.split(":", 1)[0].strip()
    for sep in ("-", "_"):
        lowered = base.lower()
        for effort in ("minimal", "low", "medium", "high"):
            suffix = f"{sep}{effort}"
            if lowered.endswith(suffix):
                base = base[: -len(suffix)]
                break
    mapping = {
        "gpt5": "gpt-5",
        "gpt-5-latest": "gpt-5",
        "gpt-5": "gpt-5",
        "gpt5-codex": "gpt-5-codex",
        "gpt-5-codex": "gpt-5-codex",
        "gpt-5-codex-latest": "gpt-5-codex",
        "codex": "codex-mini-latest",
        "codex-mini": "codex-mini-latest",
        "codex-mini-latest": "codex-mini-latest",
    }
    return mapping.get(base, base)


def start_upstream_request(  # noqa: PLR0913
    model: str,
    input_items: list[dict[str, Any]],
    *,
    instructions: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | str | None = None,
    parallel_tool_calls: bool = False,
    reasoning_param: dict[str, Any] | None = None,
) -> tuple[requests.Response | None, Response | None]:
    """Start a streaming Responses API request and return (upstream, error_response)."""
    # Import via module attribute to allow pytest monkeypatching
    access_token, account_id = utils_mod.get_effective_chatgpt_auth()
    if not access_token or not account_id:
        resp = make_response(
            jsonify(
                {
                    "error": {
                        "message": (
                            "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first."
                        ),
                    }
                }
            ),
            401,
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp

    include: list[str] = []
    if isinstance(reasoning_param, dict):
        include.append("reasoning.encrypted_content")

    client_session_id = (
        flask_request.headers.get("X-Session-Id") or flask_request.headers.get("session_id") or None
    )
    session_id = ensure_session_id(instructions, input_items, client_session_id)

    responses_payload = {
        "model": model,
        "instructions": instructions,
        "input": input_items,
        "tools": tools or [],
        "tool_choice": tool_choice
        if tool_choice in ("auto", "none") or isinstance(tool_choice, dict)
        else "auto",
        "parallel_tool_calls": bool(parallel_tool_calls),
        "store": False,
        "stream": True,
        "prompt_cache_key": session_id,
    }
    if include:
        responses_payload["include"] = include

    if reasoning_param is not None:
        responses_payload["reasoning"] = reasoning_param

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
            json=responses_payload,
            stream=True,
            timeout=600,
        )
    except requests.RequestException as e:
        resp = make_response(
            jsonify({"error": {"message": f"Upstream ChatGPT request failed: {e}"}}), 502
        )
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp
    return upstream, None
