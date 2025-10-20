"""Test to_data_url content type detection for jpeg and gif markers."""

from __future__ import annotations

from chatmock.transform import to_data_url


def test_to_data_url_jpeg_and_gif_markers() -> None:
    assert to_data_url("/9j/AAAA").startswith("data:image/jpeg;base64,")
    assert to_data_url("R0lGOD").startswith("data:image/gif;base64,")
