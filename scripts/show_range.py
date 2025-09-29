"""Utility to print a range of lines from a file."""

from __future__ import annotations

import sys
from pathlib import Path

_USAGE_MIN_ARGS = 3


def main() -> int:
    """Print lines [start, end] (1-based, inclusive) from a file path."""
    if len(sys.argv) < _USAGE_MIN_ARGS:
        sys.stdout.write("Usage: python scripts/show_range.py <path> <start> [<end>]\n")
        return 1
    p = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3]) if len(sys.argv) > _USAGE_MIN_ARGS else start
    if not p.exists():
        sys.stdout.write(f"File not found: {p}\n")
        return 1
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    for i in range(max(1, start), min(len(lines), end) + 1):
        sys.stdout.write(f"{i:4}: {lines[i - 1]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
