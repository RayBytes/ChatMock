"""Cover _should_refresh_access_token utility function."""

from __future__ import annotations

import base64
import json

from chatmock.utils import _should_refresh_access_token


def test_should_refresh_when_token_is_none() -> None:
    """Returns True when access token is None."""
    assert _should_refresh_access_token(None, None) is True


def test_should_refresh_when_token_is_empty() -> None:
    """Returns True when access token is empty string."""
    assert _should_refresh_access_token("", None) is True


def test_should_refresh_when_token_is_not_string() -> None:
    """Returns True when access token is not a string."""
    assert _should_refresh_access_token(123, None) is True  # type: ignore[arg-type]
    assert _should_refresh_access_token([], None) is True  # type: ignore[arg-type]


def test_should_refresh_with_invalid_exp_timestamp() -> None:
    """Returns False when exp timestamp is invalid and no last_refresh."""
    # Create a JWT with an impossibly large exp timestamp
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    # Use a timestamp that would cause OverflowError
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"exp": 10**20}).encode()  # Impossibly large timestamp
        )
        .decode()
        .rstrip("=")
    )
    signature = "fake"
    invalid_token = f"{header}.{payload}.{signature}"

    # Should handle the overflow gracefully and fall through to return False
    result = _should_refresh_access_token(invalid_token, None)
    # Since last_refresh is None and exp is invalid, function returns False
    assert result is False


def test_should_refresh_with_recent_last_refresh() -> None:
    """Returns False when last_refresh is recent (< 55 minutes ago)."""
    # Valid token with no exp
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({}).encode()).decode().rstrip("=")
    signature = "fake"
    token = f"{header}.{payload}.{signature}"

    # Recent timestamp (just refreshed)
    import datetime

    recent_refresh = datetime.datetime.now(datetime.timezone.utc).isoformat()

    result = _should_refresh_access_token(token, recent_refresh)
    # Should not refresh since it was just refreshed
    assert result is False


def test_should_refresh_with_old_last_refresh() -> None:
    """Returns True when last_refresh is old (>= 55 minutes ago)."""
    # Valid token with no exp
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({}).encode()).decode().rstrip("=")
    signature = "fake"
    token = f"{header}.{payload}.{signature}"

    # Old timestamp (56 minutes ago)
    import datetime

    old_refresh = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=56)
    ).isoformat()

    result = _should_refresh_access_token(token, old_refresh)
    # Should refresh since it's been > 55 minutes
    assert result is True
