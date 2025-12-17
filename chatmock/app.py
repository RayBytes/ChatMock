from __future__ import annotations

import os

from flask import Flask, jsonify, request

from .config import BASE_INSTRUCTIONS, GPT5_CODEX_INSTRUCTIONS
from .debug import cleanup_debug_files
from .http import build_cors_headers
from .routes_openai import openai_bp
from .routes_ollama import ollama_bp
from .routes_webui import webui_bp
from .routes_responses import responses_bp


def create_app(
    verbose: bool = False,
    debug_log: bool = False,
    verbose_obfuscation: bool = False,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    debug_model: str | None = None,
    expose_reasoning_models: bool = False,
    default_web_search: bool = False,
    expose_experimental_models: bool = False,
    enable_responses_api: bool = False,
    responses_no_base_instructions: bool = False,
    api_key: str | None = None,
) -> Flask:
    app = Flask(__name__)

    # Cleanup old debug files if any debug mode is enabled
    debug_bisect = os.getenv("DEBUG_INSTRUCTIONS_BISECT", "").lower() in ("1", "true", "yes", "on")
    debug_prompts = os.getenv("DEBUG_LOG_PROMPTS", "").lower() in ("1", "true", "yes", "on")
    if debug_log or debug_bisect or debug_prompts:
        cleanup_debug_files()

    app.config.update(
        VERBOSE=bool(verbose),
        DEBUG_LOG=bool(debug_log),
        VERBOSE_OBFUSCATION=bool(verbose_obfuscation),
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        DEBUG_MODEL=debug_model,
        BASE_INSTRUCTIONS=BASE_INSTRUCTIONS,
        GPT5_CODEX_INSTRUCTIONS=GPT5_CODEX_INSTRUCTIONS,
        EXPOSE_REASONING_MODELS=bool(expose_reasoning_models),
        DEFAULT_WEB_SEARCH=bool(default_web_search),
        EXPOSE_EXPERIMENTAL_MODELS=bool(expose_experimental_models),
        ENABLE_RESPONSES_API=bool(enable_responses_api),
        RESPONSES_NO_BASE_INSTRUCTIONS=bool(responses_no_base_instructions),
        API_KEY=api_key if isinstance(api_key, str) and api_key.strip() else None,
    )

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.before_request
    def _check_api_key():
        """Check API key for protected endpoints."""
        required_key = app.config.get("API_KEY")
        if not required_key:
            return None  # No key configured, allow all

        # Skip auth for health, root, OPTIONS (CORS preflight), webui and its API
        if request.method == "OPTIONS":
            return None
        path = request.path
        if path in ("/", "/health"):
            return None
        if path.startswith("/webui") or path.startswith("/api/"):
            return None

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()
        else:
            provided_key = auth_header.strip()

        if provided_key != required_key:
            resp = jsonify({"error": {"message": "Invalid API key", "code": "invalid_api_key"}})
            resp.status_code = 401
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        return None

    @app.after_request
    def _cors(resp):
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    app.register_blueprint(openai_bp)
    app.register_blueprint(ollama_bp)
    app.register_blueprint(webui_bp)

    if bool(app.config.get("ENABLE_RESPONSES_API")):
        app.register_blueprint(responses_bp)

    return app
