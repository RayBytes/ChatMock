"""HTTP helpers for CORS and error responses."""

from __future__ import annotations

from flask import Response, jsonify, request


def build_cors_headers() -> dict:
    """Return default CORS headers based on the incoming request."""
    origin = request.headers.get("Origin", "*")
    req_headers = request.headers.get("Access-Control-Request-Headers")
    allow_headers = req_headers if req_headers else "Authorization, Content-Type, Accept"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": allow_headers,
        "Access-Control-Max-Age": "86400",
    }


def json_error(message: str, status: int = 400) -> Response:
    """Build a JSON error Response with CORS headers and given status code."""
    resp = jsonify({"error": {"message": message}})
    response: Response = Response(
        response=resp.response, status=status, mimetype="application/json"
    )
    for k, v in build_cors_headers().items():
        response.headers.setdefault(k, v)
    return response
