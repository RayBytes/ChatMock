"""WebUI routes for ChatMock dashboard and configuration management"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_from_directory, current_app

from .limits import load_rate_limit_snapshot, compute_reset_at
from .utils import get_home_dir, load_chatgpt_tokens, parse_jwt_claims, read_auth_file

webui_bp = Blueprint("webui", __name__)

# Track request statistics
STATS_FILE = Path(get_home_dir()) / "stats.json"


def load_stats() -> dict[str, Any]:
    """Load usage statistics from file"""
    if not STATS_FILE.exists():
        return {
            "total_requests": 0,
            "requests_by_model": {},
            "requests_by_date": {},
            "total_tokens": 0,
            "last_request": None,
            "first_request": None,
        }
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "total_requests": 0,
            "requests_by_model": {},
            "requests_by_date": {},
            "total_tokens": 0,
            "last_request": None,
            "first_request": None,
        }


def save_stats(stats: dict[str, Any]) -> None:
    """Save usage statistics to file"""
    try:
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass


def record_request(model: str, tokens: int = 0) -> None:
    """Record a request in statistics"""
    stats = load_stats()
    now = datetime.utcnow().isoformat()
    date_key = now[:10]  # YYYY-MM-DD

    stats["total_requests"] += 1
    stats["total_tokens"] += tokens
    stats["last_request"] = now

    if stats["first_request"] is None:
        stats["first_request"] = now

    # Track by model
    if model not in stats["requests_by_model"]:
        stats["requests_by_model"][model] = 0
    stats["requests_by_model"][model] += 1

    # Track by date
    if date_key not in stats["requests_by_date"]:
        stats["requests_by_date"][date_key] = 0
    stats["requests_by_date"][date_key] += 1

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


@webui_bp.route("/api/status")
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


@webui_bp.route("/api/config", methods=["GET"])
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
    """Get OAuth login URL"""
    from .config import CLIENT_ID_DEFAULT, OAUTH_ISSUER_DEFAULT
    from .oauth import REDIRECT_URI, REQUIRED_PORT
    import secrets

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Build OAuth URL
    auth_url = (
        f"{OAUTH_ISSUER_DEFAULT}/authorize"
        f"?client_id={CLIENT_ID_DEFAULT}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid%20profile%20email%20offline_access"
        f"&state={state}"
    )

    return jsonify({
        "auth_url": auth_url,
        "state": state,
        "redirect_uri": REDIRECT_URI,
        "note": "For full OAuth flow, use the 'login' command or Docker login service",
    })
