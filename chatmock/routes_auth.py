from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, jsonify, request

from .utils import write_auth_file
from .routes_auth_utils import _validate_admin_key


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login() -> Response:
    """Handle JSON login data and save auth file"""
    # Validate admin key
    if not _validate_admin_key():
        return jsonify({"error": {"message": "Unauthorized: Invalid or missing admin key"}}), 401
    
    verbose = bool(current_app.config.get("VERBOSE"))
    
    if verbose:
        try:
            body_preview = (request.get_data(cache=True, as_text=True) or "")[:2000]
            print("IN POST /auth/login\n" + body_preview)
        except Exception:
            pass

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        try:
            payload = json.loads(raw.replace("\r", "").replace("\n", ""))
        except Exception:
            return jsonify({"error": {"message": "Invalid JSON body"}}), 400

    # Prepare auth data structure similar to oauth.py
    tokens = payload.get("tokens", {})
    auth_json_contents = {
        "OPENAI_API_KEY": payload.get("OPENAI_API_KEY"),
        "tokens": {
            "id_token": tokens.get("id_token", ""),
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "account_id": tokens.get("account_id", ""),
        },
        "last_refresh": payload.get("last_refresh", ""),
    }
    
    # Save the auth file using the existing utility function
    if write_auth_file(auth_json_contents):
        return jsonify({
            "status": "success",
            "message": "Authentication data saved successfully"
        }), 200
    else:
        return jsonify({
            "error": {"message": "Failed to save authentication data"}
        }), 500


@auth_bp.route("/status", methods=["GET"])
def auth_status() -> Response:
    """Check authentication status"""
    # Validate admin key
    if not _validate_admin_key():
        return jsonify({"error": {"message": "Unauthorized: Invalid or missing admin key"}}), 401
    
    from .utils import read_auth_file
    
    auth_data = read_auth_file()
    if auth_data:
        return jsonify({
            "status": "authenticated",
            "auth_data": auth_data
        }), 200
    else:
        return jsonify({
            "status": "unauthenticated",
            "auth_data": {}
        }), 401
