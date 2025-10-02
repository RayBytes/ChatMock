"""Contract tests pinning key response payloads for common routes."""

from __future__ import annotations

from http import HTTPStatus

from chatmock import routes_ollama, routes_openai
from tests.helpers import FakeUpstream


def _sse_lines_text(text: str) -> list[str]:
    return [
        f' data: {{"type": "response.output_text.delta", "delta": "{text}"}}'.lstrip(),
        'data: {"type": "response.completed"}',
    ]


def test_contract_openai_chat_nonstream_basic(client: object, monkeypatch: object) -> None:
    """Pins basic Chat Completions non-stream response shape and fields."""

    def _start_upstream_request(*_args: object, **_kwargs: object) -> tuple[object, None]:
        return FakeUpstream(_sse_lines_text("Hello")), None

    monkeypatch.setattr(
        routes_openai,
        "start_upstream_request",
        _start_upstream_request,
        raising=True,
    )
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-5", "messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt-5"
    assert isinstance(data["created"], int)
    choice = data["choices"][0]
    assert choice["finish_reason"] == "stop"
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "Hello"


def test_contract_openai_text_completions_nonstream_basic(
    client: object, monkeypatch: object
) -> None:
    """Pins basic Text Completions non-stream response shape and fields."""

    def _start_upstream_request2(*_args: object, **_kwargs: object) -> tuple[object, None]:
        return FakeUpstream(_sse_lines_text("Hello")), None

    monkeypatch.setattr(
        routes_openai, "start_upstream_request", _start_upstream_request2, raising=True
    )
    resp = client.post("/v1/completions", json={"model": "gpt-5", "prompt": "Hi"})
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["object"] == "text_completion"
    assert data["model"] == "gpt-5"
    assert isinstance(data["created"], int)
    choice = data["choices"][0]
    assert choice["finish_reason"] == "stop"
    assert choice["text"] == "Hello"


def test_contract_openai_models_list(client: object) -> None:
    """Pins the models listing structure and presence of core ids."""
    resp = client.get("/v1/models")
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["object"] == "list"
    ids = {m.get("id") for m in data.get("data", [])}
    assert {"gpt-5", "gpt-5-codex"}.issubset(ids)


def test_contract_ollama_chat_nonstream_basic(client: object, monkeypatch: object) -> None:
    """Pins basic Ollama chat non-stream response shape and fields."""

    def _start_upstream_request3(*_args: object, **_kwargs: object) -> tuple[object, None]:
        return FakeUpstream(_sse_lines_text("Hello")), None

    monkeypatch.setattr(
        routes_ollama, "start_upstream_request", _start_upstream_request3, raising=True
    )
    resp = client.post(
        "/api/chat",
        json={"model": "gpt-5", "messages": [{"role": "user", "content": "Hi"}], "stream": False},
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["model"] == "gpt-5"
    assert data["done"] is True
    assert data["done_reason"] == "stop"
    msg = data["message"]
    assert msg["role"] == "assistant"
    assert msg["content"] == "Hello"


def test_contract_ollama_tags(client: object) -> None:
    """Pins tags listing structure and presence of core models."""
    resp = client.get("/api/tags")
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    names = {m.get("name") for m in data.get("models", [])}
    assert {"gpt-5", "gpt-5-codex"}.issubset(names)
