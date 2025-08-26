from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple, Optional, Set
import re

import requests
from flask import Response, jsonify, make_response

from .config import (
    CHATGPT_RESPONSES_URL,
)
from .http import build_cors_headers
from .session import ensure_session_id
from flask import request as flask_request
from .utils import get_effective_chatgpt_auth


def normalize_model_name(name: str | None, debug_model: str | None = None) -> str:
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
        "codex": "codex-mini-latest",
        "codex-mini": "codex-mini-latest",
        "codex-mini-latest": "codex-mini-latest",
    }
    return mapping.get(base, base)


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
        "instructions": instructions if isinstance(instructions, str) and instructions.strip() else instructions,
        "input": input_items,
        "tools": tools or [],
        "tool_choice": tool_choice if tool_choice in ("auto", "none") or isinstance(tool_choice, dict) else "auto",
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
        resp = make_response(jsonify({"error": {"message": f"Upstream ChatGPT request failed: {e}"}}), 502)
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return None, resp
    return upstream, None


_MODEL_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0}
_MODEL_CACHE_TTL_SECS: int = 3600  # 1 hour


def _fetch_canonical_model_ids_from_codex_sources(timeout: float = 10.0) -> Set[str]:
    """
    Fetch canonical model identifiers from Codex public sources.
    """
    urls = [
        "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/src/openai_model_info.rs",
        "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/src/model_family.rs",
        "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/src/config.rs",
    ]
    pattern_any = re.compile(r'"([^"]+)"')
    pattern_keep = re.compile(r'^(?:gpt-|o[0-9]|codex-)', re.IGNORECASE)

    out: Set[str] = set()
    headers = {
        "User-Agent": "ChatMock/1.0 (+https://github.com/RayBytes/ChatMock)",
        "Accept": "text/plain,*/*;q=0.1",
    }
    for u in urls:
        try:
            r = requests.get(u, headers=headers, timeout=timeout)
            if r.status_code != 200:
                continue
            text = r.text or ""
            for m in pattern_any.finditer(text):
                s = m.group(1)
                if not isinstance(s, str):
                    continue
                if not pattern_keep.search(s):
                    continue
                # Normalize any trailing dashes (e.g., "codex-" -> "codex")
                s = s.rstrip("-")
                out.add(s)
        except Exception:
            continue
    return out


def _fetch_upstream_models() -> Optional[List[str]]:
    """
    Return canonical model ids from Codex public sources.
    """
    try:
        ids = _fetch_canonical_model_ids_from_codex_sources(timeout=10.0)
        if not ids:
            return None
        return sorted(ids)
    except Exception as e:
        try:
            print(f"[models] codex-source fetch exception: {e!r}")
        except Exception:
            pass
        return None


def get_cached_models(force_refresh: bool = False) -> Optional[List[str]]:
    """
    Return cached model list; refresh when forced or expired.
    """
    now = time.time()
    ttl = max(60, int(_MODEL_CACHE_TTL_SECS))
    cached = _MODEL_CACHE.get("data")
    ts = float(_MODEL_CACHE.get("ts") or 0.0)
    if (not force_refresh) and cached and (now - ts) < ttl:
        return cached  # type: ignore
    models = _fetch_upstream_models()
    if models:
        _MODEL_CACHE["data"] = models
        _MODEL_CACHE["ts"] = now
        return models
    # keep stale cache if present
    if cached:
        return cached  # type: ignore
    return None


def list_advertised_models(force_refresh: bool = False) -> List[str]:
    """
    Return the model list. Use force_refresh=True to bypass cache.
    """
    fetched = get_cached_models(force_refresh=bool(force_refresh))
    if not isinstance(fetched, list):
        return []
    try:
        return sorted(set([m for m in fetched if isinstance(m, str) and m.strip()]))
    except Exception:
        return [m for m in fetched if isinstance(m, str) and m.strip()]


def prefetch_models_on_startup(verbose: bool = False) -> None:
    """
    Prefetch models at startup.
    """
    models = get_cached_models(force_refresh=True)
    if verbose:
        print(f"[models] prefetch fetched={bool(models)} count={(len(models) if models else 0)}")


def fetch_upstream_models_debug() -> Tuple[Optional[List[str]], Dict[str, Any]]:
    """
    Diagnostic fetch using Codex public sources. Does not touch the cache.
    """
    debug: Dict[str, Any] = {"source": "codex_public_repo"}
    try:
        ids = _fetch_canonical_model_ids_from_codex_sources(timeout=10.0)
        models = sorted(ids)
        debug["parsed_count"] = len(models)
        return (models if models else None), debug
    except Exception as e:
        debug.update({"exception": repr(e)})
        return None, debug
