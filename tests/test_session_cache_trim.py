"""Exercise session cache trimming when exceeding max entries."""

from __future__ import annotations

import chatmock.session as sess


def test_session_cache_trimming(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sess, "_MAX_ENTRIES", 1, raising=True)
    # Reset caches to avoid interference from other tests
    sess._FINGERPRINT_TO_UUID.clear()
    sess._ORDER.clear()
    items = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "A"}]}]
    s1 = sess.ensure_session_id("i1", items, None)
    s2 = sess.ensure_session_id("i2", items, None)
    # First fingerprint should be evicted; requesting for i1 again should produce a new id
    s1b = sess.ensure_session_id("i1", items, None)
    assert s1 != s1b and s2
