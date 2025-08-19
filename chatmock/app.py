from __future__ import annotations

from flask import Flask, jsonify

from .config import BASE_INSTRUCTIONS
from .http import build_cors_headers
from .routes_openai import openai_bp
from .routes_ollama import ollama_bp
from .routes_auth import auth_bp
from .routes_auth_utils import _get_or_generate_admin_key


def create_app(
    verbose: bool = False,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    debug_model: str | None = None,
) -> Flask:
    app = Flask(__name__)

    app.config.update(
        VERBOSE=bool(verbose),
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        DEBUG_MODEL=debug_model,
        BASE_INSTRUCTIONS=BASE_INSTRUCTIONS,
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

    _get_or_generate_admin_key()
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app

