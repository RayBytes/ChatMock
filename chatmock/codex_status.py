from __future__ import annotations

import os
from typing import Any, Dict

from .limits import StoredRateLimitSnapshot, load_rate_limit_snapshot
from .utils import auth_file_candidates, load_chatgpt_tokens, parse_jwt_claims

_OPENAI_AUTH_CLAIM = "https://api.openai.com/auth"

# The account claims only change when the auth file does, so the derived
# info is cached against its mtime/size: a request pays one os.stat per
# candidate path, not a read + JSON parse + JWT decode.
_CACHE_UNSET: Any = object()
_account_cache_key: Any = _CACHE_UNSET
_account_cache: Dict[str, str] = {}


def _auth_files_state() -> tuple:
    state = []
    for path in auth_file_candidates():
        try:
            st = os.stat(path)
        except OSError:
            continue
        state.append((path, st.st_mtime_ns, st.st_size))
    return tuple(state)


def reset_account_info_cache() -> None:
    global _account_cache_key, _account_cache
    _account_cache_key = _CACHE_UNSET
    _account_cache = {}


def account_info() -> Dict[str, str]:
    """Display metadata about the signed-in account, derived from token claims.

    Never carries a token, and never a claim set wholesale: only the display
    values, each omitted when its claim is unavailable.
    """
    global _account_cache_key, _account_cache
    key = _auth_files_state()
    if key == _account_cache_key:
        return dict(_account_cache)
    info = _compute_account_info()
    _account_cache_key = key
    _account_cache = info
    return dict(info)


def _display_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _compute_account_info() -> Dict[str, str]:
    try:
        access_token, account_id, id_token = load_chatgpt_tokens(ensure_fresh=False)
    except Exception:
        return {}
    id_claims = parse_jwt_claims(id_token) if isinstance(id_token, str) else None
    access_claims = parse_jwt_claims(access_token) if isinstance(access_token, str) else None
    id_claims = id_claims if isinstance(id_claims, dict) else {}
    access_claims = access_claims if isinstance(access_claims, dict) else {}

    info: Dict[str, str] = {}

    email = _display_str(id_claims.get("email"))
    name = None
    for candidate in (id_claims.get("name"), id_claims.get("email"), id_claims.get("preferred_username"), account_id):
        name = _display_str(candidate)
        if name:
            break
    if name:
        info["name"] = name
    if email:
        info["email"] = email

    auth_claims = access_claims.get(_OPENAI_AUTH_CLAIM)
    if isinstance(auth_claims, dict):
        plan = _display_str(auth_claims.get("chatgpt_plan_type"))
        if plan:
            info["plan_type"] = plan

    safe_account_id = _display_str(account_id)
    if safe_account_id:
        info["account_id"] = safe_account_id
    return info


def _window_payload(window: Any) -> Dict[str, Any] | None:
    if window is None:
        return None
    return {
        "used_percent": window.used_percent,
        "window_minutes": window.window_minutes,
        "resets_in_seconds": window.resets_in_seconds,
    }


def build_status_payload() -> Dict[str, Any]:
    """The signed-in account and the last usage snapshot Codex reported.

    The usage half mirrors the CLI's `info` command: it is the snapshot
    recorded from the most recent proxied request, not a live probe — the
    Codex backend only reports usage on replies it sends.
    """
    account = account_info() or None

    stored: StoredRateLimitSnapshot | None = load_rate_limit_snapshot()
    rate_limits: Dict[str, Any] | None = None
    if stored is not None:
        rate_limits = {
            "captured_at": stored.captured_at.isoformat(),
            "primary": _window_payload(stored.snapshot.primary),
            "secondary": _window_payload(stored.snapshot.secondary),
        }

    return {"account": account, "rate_limits": rate_limits}
