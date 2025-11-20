"""WebUI routes for ChatMock dashboard and configuration management"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_from_directory, current_app, make_response

from .limits import load_rate_limit_snapshot, compute_reset_at
from .utils import get_home_dir, load_chatgpt_tokens, parse_jwt_claims, read_auth_file

webui_bp = Blueprint("webui", __name__)

# Track request statistics
STATS_FILE = Path(get_home_dir()) / "stats.json"

# Session tokens for WebUI auth (in-memory)
_webui_sessions = set()


def check_webui_auth():
    """Check if request is authenticated for WebUI access"""
    password = os.getenv("WEBUI_PASSWORD", "")
    if not password:
        return True  # No password set, allow access

    session_token = request.cookies.get("webui_session")
    return session_token in _webui_sessions


def require_webui_auth(f):
    """Decorator to require WebUI authentication"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_webui_auth():
            return jsonify({"error": "Authentication required", "auth_required": True}), 401
        return f(*args, **kwargs)
    return decorated


def load_stats() -> dict[str, Any]:
    """Load usage statistics from file"""
    default_stats = {
        "total_requests": 0,
        "total_successful": 0,
        "total_failed": 0,
        "requests_by_model": {},
        "requests_by_endpoint": {},
        "requests_by_date": {},
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "tokens_by_model": {},
        "avg_response_time": 0,
        "total_response_time": 0,
        "last_request": None,
        "first_request": None,
        "recent_requests": [],  # Last 100 requests
    }
    if not STATS_FILE.exists():
        return default_stats
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
            # Ensure all keys exist (for backward compatibility)
            for key, value in default_stats.items():
                if key not in stats:
                    stats[key] = value
            return stats
    except Exception:
        return default_stats


def save_stats(stats: dict[str, Any]) -> None:
    """Save usage statistics to file"""
    try:
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def record_request(
    model: str,
    endpoint: str = "unknown",
    success: bool = True,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    response_time: float = 0.0,
    error_message: str | None = None,
) -> None:
    """Record a request in statistics with detailed metrics"""
    stats = load_stats()
    now = datetime.utcnow().isoformat()
    date_key = now[:10]  # YYYY-MM-DD

    # Update counters
    stats["total_requests"] += 1
    if success:
        stats["total_successful"] += 1
    else:
        stats["total_failed"] += 1

    # Update token counters
    if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
        total_tokens = prompt_tokens + completion_tokens

    stats["total_tokens"] += total_tokens
    stats["total_prompt_tokens"] += prompt_tokens
    stats["total_completion_tokens"] += completion_tokens

    # Update timing
    stats["total_response_time"] += response_time
    if stats["total_requests"] > 0:
        stats["avg_response_time"] = stats["total_response_time"] / stats["total_requests"]

    stats["last_request"] = now
    if stats["first_request"] is None:
        stats["first_request"] = now

    # Track by model
    if model not in stats["requests_by_model"]:
        stats["requests_by_model"][model] = 0
    stats["requests_by_model"][model] += 1

    # Track tokens by model
    if model not in stats["tokens_by_model"]:
        stats["tokens_by_model"][model] = {
            "total": 0,
            "prompt": 0,
            "completion": 0,
        }
    stats["tokens_by_model"][model]["total"] += total_tokens
    stats["tokens_by_model"][model]["prompt"] += prompt_tokens
    stats["tokens_by_model"][model]["completion"] += completion_tokens

    # Track by endpoint
    if endpoint not in stats["requests_by_endpoint"]:
        stats["requests_by_endpoint"][endpoint] = 0
    stats["requests_by_endpoint"][endpoint] += 1

    # Track by date
    if date_key not in stats["requests_by_date"]:
        stats["requests_by_date"][date_key] = 0
    stats["requests_by_date"][date_key] += 1

    # Add to recent requests (keep last 100)
    request_record = {
        "timestamp": now,
        "model": model,
        "endpoint": endpoint,
        "success": success,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "response_time": response_time,
        "error": error_message,
    }
    stats["recent_requests"].insert(0, request_record)
    stats["recent_requests"] = stats["recent_requests"][:100]  # Keep last 100

    save_stats(stats)


@webui_bp.route("/webui")
@webui_bp.route("/webui/")
def index():
    """Serve the WebUI index page"""
    return send_from_directory("webui/dist", "index.html")


@webui_bp.route("/webui/<path:path>")
def serve_webui(path):
    """Serve WebUI static files"""
    return send_from_directory("webui/dist", path)


@webui_bp.route("/api/webui-auth", methods=["GET"])
def api_webui_auth_check():
    """Check if WebUI password is required and current auth status"""
    password = os.getenv("WEBUI_PASSWORD", "")
    return jsonify({
        "password_required": bool(password),
        "authenticated": check_webui_auth(),
    })


@webui_bp.route("/api/webui-auth", methods=["POST"])
def api_webui_auth_login():
    """Authenticate with WebUI password"""
    password = os.getenv("WEBUI_PASSWORD", "")
    if not password:
        return jsonify({"success": True, "message": "No password required"})

    data = request.get_json() or {}
    provided = data.get("password", "")

    if provided == password:
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        _webui_sessions.add(session_token)

        response = make_response(jsonify({"success": True}))
        response.set_cookie(
            "webui_session",
            session_token,
            httponly=True,
            samesite="Lax",
            max_age=86400 * 7  # 7 days
        )
        return response
    else:
        return jsonify({"success": False, "error": "Invalid password"}), 401


@webui_bp.route("/api/status")
@require_webui_auth
def api_status():
    """Get server status and authentication info"""
    access_token, account_id, id_token = load_chatgpt_tokens()

    authenticated = bool(access_token and id_token)
    user_info = None

    if authenticated:
        id_claims = parse_jwt_claims(id_token) or {}
        access_claims = parse_jwt_claims(access_token) or {}

        email = id_claims.get("email") or id_claims.get("preferred_username") or "unknown"
        plan_raw = (access_claims.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type") or "unknown"
        plan_map = {
            "plus": "Plus",
            "pro": "Pro",
            "free": "Free",
            "team": "Team",
            "enterprise": "Enterprise",
        }
        plan = plan_map.get(str(plan_raw).lower(), str(plan_raw).title() if isinstance(plan_raw, str) else "Unknown")

        user_info = {
            "email": email,
            "plan": plan,
            "account_id": account_id,
        }

    return jsonify({
        "status": "ok",
        "authenticated": authenticated,
        "user": user_info,
        "version": "1.0.0",
    })


@webui_bp.route("/api/stats")
@require_webui_auth
def api_stats():
    """Get usage statistics"""
    stats = load_stats()

    # Get rate limit info
    rate_limits = None
    stored = load_rate_limit_snapshot()
    if stored is not None:
        rate_limits = {
            "captured_at": stored.captured_at.isoformat(),
            "primary": None,
            "secondary": None,
        }

        if stored.snapshot.primary is not None:
            window = stored.snapshot.primary
            rate_limits["primary"] = {
                "used_percent": window.used_percent,
                "resets_in_seconds": window.resets_in_seconds,
                "reset_at": compute_reset_at(stored.captured_at, window).isoformat() if compute_reset_at(stored.captured_at, window) else None,
            }

        if stored.snapshot.secondary is not None:
            window = stored.snapshot.secondary
            rate_limits["secondary"] = {
                "used_percent": window.used_percent,
                "resets_in_seconds": window.resets_in_seconds,
                "reset_at": compute_reset_at(stored.captured_at, window).isoformat() if compute_reset_at(stored.captured_at, window) else None,
            }

    return jsonify({
        **stats,
        "rate_limits": rate_limits,
    })


@webui_bp.route("/api/models")
@require_webui_auth
def api_models():
    """Get list of available models"""
    expose_reasoning = current_app.config.get("EXPOSE_REASONING_MODELS", False)

    # Define model information based on routes_openai.py structure
    model_info = {
        "gpt-5": {
            "name": "GPT-5",
            "description": "Latest flagship model from OpenAI with advanced reasoning capabilities",
            "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
            "efforts": ["high", "medium", "low", "minimal"],
        },
        "gpt-5.1": {
            "name": "GPT-5.1",
            "description": "Enhanced version of GPT-5 with improved capabilities",
            "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
            "efforts": ["high", "medium", "low", "minimal"],
        },
        "gpt-5-codex": {
            "name": "GPT-5 Codex",
            "description": "Specialized model optimized for coding tasks",
            "capabilities": ["reasoning", "function_calling", "coding"],
            "efforts": ["high", "medium", "low"],
        },
        "gpt-5.1-codex": {
            "name": "GPT-5.1 Codex",
            "description": "Enhanced coding model with improved capabilities",
            "capabilities": ["reasoning", "function_calling", "coding"],
            "efforts": ["high", "medium", "low"],
        },
        "gpt-5.1-codex-mini": {
            "name": "GPT-5.1 Codex Mini",
            "description": "Lightweight enhanced coding model for faster responses",
            "capabilities": ["coding", "function_calling"],
            "efforts": [],
        },
        "codex-mini": {
            "name": "Codex Mini",
            "description": "Lightweight variant for faster coding responses",
            "capabilities": ["coding", "function_calling"],
            "efforts": [],
        },
    }

    models_list = []
    for model_id, info in model_info.items():
        models_list.append({
            "id": model_id,
            "name": info["name"],
            "description": info["description"],
            "capabilities": info["capabilities"],
        })

        # Add reasoning variants if enabled
        if expose_reasoning and info["efforts"]:
            for effort in info["efforts"]:
                models_list.append({
                    "id": f"{model_id}-{effort}",
                    "name": f"{info['name']} ({effort.title()} Reasoning)",
                    "description": f"{info['description']} - {effort} reasoning effort",
                    "capabilities": info["capabilities"],
                })

    return jsonify({"models": models_list})


@webui_bp.route("/api/request-history")
@require_webui_auth
def api_request_history():
    """Get recent request history"""
    stats = load_stats()
    limit = request.args.get("limit", "50")
    try:
        limit = int(limit)
        limit = min(max(1, limit), 100)  # Clamp between 1-100
    except (ValueError, TypeError):
        limit = 50

    recent = stats.get("recent_requests", [])[:limit]
    return jsonify({
        "requests": recent,
        "total_count": len(stats.get("recent_requests", [])),
    })


@webui_bp.route("/api/config", methods=["GET"])
@require_webui_auth
def api_config_get():
    """Get current configuration"""
    config = {
        "verbose": current_app.config.get("VERBOSE", False),
        "reasoning_effort": current_app.config.get("REASONING_EFFORT", "medium"),
        "reasoning_summary": current_app.config.get("REASONING_SUMMARY", "auto"),
        "reasoning_compat": current_app.config.get("REASONING_COMPAT", "think-tags"),
        "expose_reasoning_models": current_app.config.get("EXPOSE_REASONING_MODELS", False),
        "default_web_search": current_app.config.get("DEFAULT_WEB_SEARCH", False),
        "debug_model": current_app.config.get("DEBUG_MODEL"),
        "port": os.getenv("PORT", "8000"),
    }
    return jsonify(config)


@webui_bp.route("/api/config", methods=["POST"])
@require_webui_auth
def api_config_update():
    """Update configuration (runtime only, does not persist to env)"""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    # Update runtime configuration
    updatable_fields = {
        "verbose": "VERBOSE",
        "reasoning_effort": "REASONING_EFFORT",
        "reasoning_summary": "REASONING_SUMMARY",
        "reasoning_compat": "REASONING_COMPAT",
        "expose_reasoning_models": "EXPOSE_REASONING_MODELS",
        "default_web_search": "DEFAULT_WEB_SEARCH",
        "debug_model": "DEBUG_MODEL",
    }

    updated = []
    for field, config_key in updatable_fields.items():
        if field in data:
            current_app.config[config_key] = data[field]
            updated.append(field)

    return jsonify({
        "success": True,
        "updated": updated,
        "message": "Configuration updated. Note: Changes are runtime only and will reset on restart. Update environment variables for persistent changes.",
    })


@webui_bp.route("/api/login-url")
def api_login_url():
    """Get OAuth login URL for authentication"""
    from .config import CLIENT_ID_DEFAULT, OAUTH_ISSUER_DEFAULT
    from .oauth import REQUIRED_PORT
    from .utils import generate_pkce
    import urllib.parse

    # Generate PKCE codes
    pkce = generate_pkce()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    redirect_uri = f"http://localhost:{REQUIRED_PORT}/auth/callback"

    # Build OAuth URL with proper parameters
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID_DEFAULT,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access",
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }

    auth_url = f"{OAUTH_ISSUER_DEFAULT}/oauth/authorize?{urllib.parse.urlencode(params)}"

    return jsonify({
        "auth_url": auth_url,
        "note": "Open this URL to authenticate. The callback requires the login service on port 1455.",
    })
