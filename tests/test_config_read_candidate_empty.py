"""Test _read_candidate with empty file content."""

from __future__ import annotations

from pathlib import Path

from chatmock import config


def test_read_candidate_empty_content(tmp_path: Path) -> None:
    """Test _read_candidate returns None for empty/whitespace-only content."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")

    content, err = config._read_candidate(empty_file)

    assert content is None
    assert err is None


def test_read_candidate_whitespace_only(tmp_path: Path) -> None:
    """Test _read_candidate returns None for whitespace-only content."""
    whitespace_file = tmp_path / "whitespace.txt"
    whitespace_file.write_text("   \n\t  \n")

    content, err = config._read_candidate(whitespace_file)

    assert content is None
    assert err is None
