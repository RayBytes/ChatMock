from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/show_range.py <path> <start> [<end>]")
        return 1
    p = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3]) if len(sys.argv) > 3 else start
    if not p.exists():
        print(f"File not found: {p}")
        return 1
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    for i in range(max(1, start), min(len(lines), end) + 1):
        print(f"{i:4}: {lines[i - 1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
