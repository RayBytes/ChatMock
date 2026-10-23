from __future__ import annotations

import os

from flask import Flask, jsonify
from flask_sock import Sock

from .http import build_cors_headers
from .model_catalog import DEFAULT_REFRESH_INTERVAL_SECONDS, ModelCatalog
from .routes_openai import openai_bp
from .routes_ollama import ollama_bp
from .websocket_routes import register_websocket_routes


def create_app(
    verbose: bool = False,
    verbose_obfuscation: bool = False,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    fast_mode: bool = False,
    debug_model: str | None = None,
    expose_reasoning_models: bool = False,
    default_web_search: bool = False,
    model_sync: bool | None = None,
    model_refresh_interval: float | None = None,
    fallback_on_429: bool | None = None,
    fallback_model: str | None = None,
) -> Flask:
    app = Flask(__name__)
    if model_sync is None:
        model_sync = (os.getenv("CHATGPT_LOCAL_MODEL_SYNC") or "true").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    if model_refresh_interval is None:
        try:
            model_refresh_interval = float(
                os.getenv("CHATGPT_LOCAL_MODEL_REFRESH_INTERVAL", DEFAULT_REFRESH_INTERVAL_SECONDS)
            )
        except (TypeError, ValueError):
            model_refresh_interval = DEFAULT_REFRESH_INTERVAL_SECONDS
    if fallback_on_429 is None:
        fallback_on_429 = (os.getenv("CHATGPT_LOCAL_FALLBACK_ON_429") or "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    if fallback_model is None:
        fallback_model = os.getenv("CHATGPT_LOCAL_429_FALLBACK_MODEL", "gpt-reserve").strip()

    app.config.update(
        VERBOSE=bool(verbose),
        VERBOSE_OBFUSCATION=bool(verbose_obfuscation),
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        FAST_MODE=bool(fast_mode),
        DEBUG_MODEL=debug_model,
        EXPOSE_REASONING_MODELS=bool(expose_reasoning_models),
        DEFAULT_WEB_SEARCH=bool(default_web_search),
        MODEL_SYNC=bool(model_sync),
        MODEL_REFRESH_INTERVAL=float(model_refresh_interval),
        FALLBACK_ON_429=bool(fallback_on_429),
        FALLBACK_MODEL=fallback_model,
    )
    app.extensions["chatmock_model_catalog"] = ModelCatalog(
        enabled=bool(model_sync),
        refresh_interval_seconds=float(model_refresh_interval),
    )

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.after_request
    def _cors(resp):
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    app.register_blueprint(openai_bp)
    app.register_blueprint(ollama_bp)
    sock = Sock(app)
    register_websocket_routes(sock)

    return app
