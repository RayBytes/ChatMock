"""WebUI routes for ChatMock dashboard and configuration management"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_from_directory, current_app

from .limits import load_rate_limit_snapshot, compute_reset_at
from .utils import get_home_dir, load_chatgpt_tokens, parse_jwt_claims, read_auth_file

webui_bp = Blueprint("webui", __name__)

# Track request statistics
STATS_FILE = Path(get_home_dir()) / "stats.json"

# Store PKCE codes for OAuth flow (in-memory, single user)
_oauth_state = {
    "pkce": None,
    "state": None,
    "redirect_uri": None,
}


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
    expose_gpt51 = current_app.config.get("EXPOSE_GPT51_MODELS", False)

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
            "description": "Enhanced version of GPT-5 with improved capabilities (experimental)",
            "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
            "efforts": ["high", "medium", "low", "minimal"],
            "experimental": True,
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
        # Skip gpt-5.1 models if not explicitly enabled
        if info.get("experimental") and not expose_gpt51:
            continue

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
        "expose_gpt51_models": current_app.config.get("EXPOSE_GPT51_MODELS", False),
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
        "expose_gpt51_models": "EXPOSE_GPT51_MODELS",
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
    from .utils import generate_pkce
    import urllib.parse

    global _oauth_state

    # Generate PKCE codes
    pkce = generate_pkce()

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Use main server port for callback (get from request)
    port = os.getenv("PORT", "8000")
    redirect_uri = f"http://localhost:{port}/auth/callback"

    # Store for callback verification
    _oauth_state["pkce"] = pkce
    _oauth_state["state"] = state
    _oauth_state["redirect_uri"] = redirect_uri

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
    })


@webui_bp.route("/auth/callback")
def auth_callback():
    """Handle OAuth callback and exchange code for tokens"""
    from .config import CLIENT_ID_DEFAULT, OAUTH_ISSUER_DEFAULT
    from .utils import write_auth_file
    import urllib.request
    import ssl
    import certifi

    global _oauth_state

    # Get code and state from query params
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"""
        <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1 style="color: #ef4444;">Authentication Failed</h1>
        <p>Error: {error}</p>
        <p>{request.args.get('error_description', '')}</p>
        <p><a href="/webui">Return to WebUI</a></p>
        </body></html>
        """, 400

    if not code:
        return """
        <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1 style="color: #ef4444;">Authentication Failed</h1>
        <p>No authorization code received</p>
        <p><a href="/webui">Return to WebUI</a></p>
        </body></html>
        """, 400

    # Verify state
    if state != _oauth_state.get("state"):
        return """
        <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1 style="color: #ef4444;">Authentication Failed</h1>
        <p>Invalid state parameter (CSRF protection)</p>
        <p><a href="/webui">Return to WebUI</a></p>
        </body></html>
        """, 400

    pkce = _oauth_state.get("pkce")
    redirect_uri = _oauth_state.get("redirect_uri")

    if not pkce or not redirect_uri:
        return """
        <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1 style="color: #ef4444;">Authentication Failed</h1>
        <p>OAuth session expired. Please try again.</p>
        <p><a href="/webui">Return to WebUI</a></p>
        </body></html>
        """, 400

    try:
        # Exchange code for tokens
        token_endpoint = f"{OAUTH_ISSUER_DEFAULT}/oauth/token"
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": CLIENT_ID_DEFAULT,
            "code_verifier": pkce.code_verifier,
        }).encode()

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        req = urllib.request.Request(
            token_endpoint,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req, context=ssl_context) as resp:
            payload = json.loads(resp.read().decode())

        id_token = payload.get("id_token", "")
        access_token = payload.get("access_token", "")
        refresh_token = payload.get("refresh_token", "")

        # Parse tokens
        id_token_claims = parse_jwt_claims(id_token) or {}
        auth_claims = id_token_claims.get("https://api.openai.com/auth", {})
        chatgpt_account_id = auth_claims.get("chatgpt_account_id", "")

        # Save auth data
        import datetime
        auth_json = {
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "account_id": chatgpt_account_id,
            },
            "last_refresh": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if write_auth_file(auth_json):
            # Clear OAuth state
            _oauth_state["pkce"] = None
            _oauth_state["state"] = None
            _oauth_state["redirect_uri"] = None

            return """
            <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
            <h1 style="color: #22c55e;">Authentication Successful!</h1>
            <p>You are now logged in to ChatMock.</p>
            <p>Redirecting to dashboard...</p>
            <script>setTimeout(() => window.location.href = '/webui', 2000);</script>
            </body></html>
            """
        else:
            return """
            <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
            <h1 style="color: #ef4444;">Authentication Failed</h1>
            <p>Failed to save authentication data</p>
            <p><a href="/webui">Return to WebUI</a></p>
            </body></html>
            """, 500

    except Exception as e:
        return f"""
        <html><body style="font-family: system-ui; max-width: 600px; margin: 80px auto; text-align: center;">
        <h1 style="color: #ef4444;">Authentication Failed</h1>
        <p>Token exchange error: {str(e)}</p>
        <p><a href="/webui">Return to WebUI</a></p>
        </body></html>
        """, 500
