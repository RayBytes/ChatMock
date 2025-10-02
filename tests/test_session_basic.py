"""Tests for session id derivation and canonicalization."""

from __future__ import annotations

from chatmock.session import canonicalize_prefix, ensure_session_id


def test_canonicalize_and_session_id_stable() -> None:
    instr = "Do it"
    items = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}]
    canon = canonicalize_prefix(instr, items)
    assert canon
    sid1 = ensure_session_id(instr, items, None)
    sid2 = ensure_session_id(instr, items, None)
    assert sid1 == sid2

    # Different content should produce a different id
    sid3 = ensure_session_id("Other", items, None)
    assert sid3 != sid1
