"""Extra session tests for client-supplied id path."""

from __future__ import annotations

from chatmock.session import ensure_session_id


def test_ensure_session_id_client_supplied_wins() -> None:
    sid = ensure_session_id(None, [], "  abc-123  ")
    assert sid == "abc-123"
