"""Exercise status coercion paths in chat completions error handling."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING

import chatmock.routes_openai as routes

if TYPE_CHECKING:  # pragma: no cover - typing aid only
    import pytest


class _BadStatus:
    def __ge__(self, other: object) -> bool:
        return True

    def __lt__(self, other: object) -> bool:
        return False

    def __int__(self) -> int:
        raise TypeError("no int")

    def __str__(self) -> str:  # pragma: no cover - logging helper
        return "bad"


class _Upstream:
    def __init__(self, status: object) -> None:
        self.status_code = status
        self.headers = {}
        self.content = b""
        self.text = "bad"

    def close(self) -> None:
        return None


def _request_body(extra: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": "gpt-5",
        "messages": [{"role": "user", "content": "hi"}],
    }
    if extra:
        payload.update(extra)
    return payload


def test_chat_completions_normalizes_invalid_status(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream = _Upstream(_BadStatus())

    def fake_start(*_a, **_k):  # type: ignore[no-untyped-def]
        return upstream, None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    resp = client.post(
        "/v1/chat/completions",
        data=json.dumps(_request_body()),
        content_type="application/json",
    )
    assert resp.status_code == HTTPStatus.BAD_GATEWAY


def test_chat_completions_retry_normalizes_status(
    client: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _Upstream(_BadStatus())
    second = _Upstream(_BadStatus())
    calls: list[str] = []

    def fake_start(*_a, **_k):  # type: ignore[no-untyped-def]
        if not calls:
            calls.append("first")
            return first, None
        calls.append("second")
        return second, None

    monkeypatch.setattr(routes, "start_upstream_request", fake_start, raising=True)
    resp = client.post(
        "/v1/chat/completions",
        data=json.dumps(
            _request_body(
                {
                    "responses_tools": [{"type": "web_search", "name": "web_search"}],
                    "tools": [
                        {
                            "type": "function",
                            "function": {"name": "web_search", "parameters": {}},
                        }
                    ],
                }
            )
        ),
        content_type="application/json",
    )
    body = resp.get_json()
    assert resp.status_code == HTTPStatus.BAD_GATEWAY
    assert body["error"]["code"] == "RESPONSES_TOOLS_REJECTED"
