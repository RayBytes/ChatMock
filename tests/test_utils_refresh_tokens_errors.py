"""Cover error and success paths in _refresh_chatgpt_tokens."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest import mock

import requests

from chatmock import utils

if TYPE_CHECKING:
    import pytest


def test_refresh_tokens_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When network request fails, return None."""

    def mock_post(*_: object, **__: object) -> None:
        raise requests.RequestException("Network error")

    monkeypatch.setattr(requests, "post", mock_post)

    result = utils._refresh_chatgpt_tokens("test_refresh", "test_client")
    assert result is None


def test_refresh_tokens_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """When HTTP status is 400+, return None."""
    mock_response = mock.Mock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST

    monkeypatch.setattr(requests, "post", lambda *_, **__: mock_response)

    result = utils._refresh_chatgpt_tokens("test_refresh", "test_client")
    assert result is None


def test_refresh_tokens_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """When response JSON is invalid, return None."""
    mock_response = mock.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.side_effect = ValueError("Invalid JSON")

    monkeypatch.setattr(requests, "post", lambda *_, **__: mock_response)

    result = utils._refresh_chatgpt_tokens("test_refresh", "test_client")
    assert result is None


def test_refresh_tokens_missing_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """When response missing required tokens, return None."""
    mock_response = mock.Mock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"missing": "tokens"}

    monkeypatch.setattr(requests, "post", lambda *_, **__: mock_response)

    result = utils._refresh_chatgpt_tokens("test_refresh", "test_client")
    assert result is None


def test_refresh_tokens_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When refresh succeeds, return token bundle."""
    mock_response = mock.Mock()
    mock_response.status_code = HTTPStatus.OK
    # Test tokens (not real credentials)
    test_id_token = "eyJhbGciOiJIUzI1NiJ9.e30.ZRrHA1JJJW8opsbCGfG_HACGpVUMN_a9IV7pAx_Zmeo"  # noqa: S105
    test_access = "test_access_token"
    test_refresh = "new_refresh_token"
    mock_response.json.return_value = {
        "id_token": test_id_token,
        "access_token": test_access,
        "refresh_token": test_refresh,
    }

    monkeypatch.setattr(requests, "post", lambda *_, **__: mock_response)
    monkeypatch.setattr(utils, "_derive_account_id", lambda _: "test_account_id")

    result = utils._refresh_chatgpt_tokens("old_refresh", "test_client")
    assert result is not None
    assert result["id_token"] == test_id_token
    assert result["access_token"] == test_access
    assert result["refresh_token"] == test_refresh
    assert result["account_id"] == "test_account_id"
