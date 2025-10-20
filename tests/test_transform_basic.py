"""Tests for chatmock.transform helpers."""

from __future__ import annotations

from chatmock.transform import to_data_url


def test_to_data_url_passthroughs() -> None:
    assert to_data_url("http://example.com/a.png").startswith("http://")
    already = "data:image/png;base64,AAA"
    assert to_data_url(already) == already


def test_to_data_url_from_base64() -> None:
    # png-like base64 prefix should be recognized
    b64 = "iVBORw0KGgo" + "A" * 12
    out = to_data_url(b64)
    assert out.startswith("data:image/png;base64,")
