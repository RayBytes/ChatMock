"""Tests for HTTP CORS helpers."""

from __future__ import annotations

import pytest

try:
    from chatmock.http import build_cors_headers
except ImportError:  # pragma: no cover - handled via skip at runtime
    build_cors_headers = None  # type: ignore[assignment]


def test_build_cors_headers_defaults(client: object) -> None:
    """Default values when no request headers are present."""
    if build_cors_headers is None:
        pytest.fail("Flask not available; this test must run")
    with client.application.test_request_context("/", headers={}):
        headers = build_cors_headers()
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "Authorization" in headers["Access-Control-Allow-Headers"]
        assert headers["Access-Control-Allow-Methods"] == "POST, GET, OPTIONS"
