"""Lightweight data models for ChatMock."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenData:
    """Auth tokens associated with a ChatGPT account."""

    id_token: str
    access_token: str
    refresh_token: str
    account_id: str


@dataclass
class AuthBundle:
    """Serialized token bundle with last-refresh timestamp."""

    api_key: str | None
    token_data: TokenData
    last_refresh: str


@dataclass
class PkceCodes:
    """PKCE code/verifier pair used during OAuth flows."""

    code_verifier: str
    code_challenge: str
