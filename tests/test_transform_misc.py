"""Extra coverage for transform helpers edge cases."""

from __future__ import annotations

from chatmock.transform import to_data_url


def test_to_data_url_unknown_prefix_passthrough() -> None:
    s = to_data_url("not-b64-or-url")
    assert s.startswith("data:image/png;base64,") and s.endswith("not-b64-or-url")
