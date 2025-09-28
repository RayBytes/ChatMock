from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/show_with_lines.py <path>")
        return 1
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"File not found: {p}")
        return 1
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        print(f"{i:4}: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
