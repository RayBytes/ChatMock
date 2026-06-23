from __future__ import annotations

from typing import Any

from flask import Response, jsonify, request


def build_cors_headers() -> dict:
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
    resp = jsonify(openai_error_payload(message))
    response: Response = Response(response=resp.response, status=status, mimetype="application/json")
    for k, v in build_cors_headers().items():
        response.headers.setdefault(k, v)
    return response


def openai_error_payload(
    message: str,
    *,
    error_type: str = "invalid_request_error",
    param: str | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }
