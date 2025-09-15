from __future__ import annotations

from flask import Flask, jsonify

from .config import BASE_INSTRUCTIONS
from .http import build_cors_headers
from .routes_openai import openai_bp
from .routes_ollama import ollama_bp


def create_app(
    verbose: bool = False,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    debug_model: str | None = None,
    expose_reasoning_models: bool = False,
    default_web_search: bool = False,
) -> Flask:
    app = Flask(__name__)

    app.config.update(
        VERBOSE=bool(verbose),
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        DEBUG_MODEL=debug_model,
        BASE_INSTRUCTIONS=BASE_INSTRUCTIONS,
        EXPOSE_REASONING_MODELS=bool(expose_reasoning_models),
        DEFAULT_WEB_SEARCH=bool(default_web_search),
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

    return app
