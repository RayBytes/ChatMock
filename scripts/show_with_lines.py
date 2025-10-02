"""Show a file with line numbers."""

from __future__ import annotations

import sys
from pathlib import Path

_EXPECTED_ARGS = 2


def main() -> int:
    """Print each line of the file with its 1-based line number."""
    if len(sys.argv) != _EXPECTED_ARGS:
        sys.stdout.write("Usage: python scripts/show_with_lines.py <path>\n")
        return 1
    p = Path(sys.argv[1])
    if not p.exists():
        sys.stdout.write(f"File not found: {p}\n")
        return 1
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        sys.stdout.write(f"{i:4}: {line}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
