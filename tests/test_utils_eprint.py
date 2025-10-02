"""Test eprint helper writes to stderr."""

from __future__ import annotations

import io
import sys

from chatmock.utils import eprint


def test_eprint_stderr() -> None:
    old = sys.stderr
    buf = io.StringIO()
    sys.stderr = buf
    try:
        eprint("x", "y")
    finally:
        sys.stderr = old
    assert "x y" in buf.getvalue()
