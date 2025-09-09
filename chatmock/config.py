from __future__ import annotations

import os
import sys
from pathlib import Path


CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"

CHATGPT_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"


def read_base_instructions() -> str:
    candidates = [
        Path(__file__).parent.parent / "prompt.md",
        Path(__file__).parent / "prompt.md",
        Path(getattr(sys, "_MEIPASS", "")) / "prompt.md" if getattr(sys, "_MEIPASS", None) else None,
        Path.cwd() / "prompt.md",
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except Exception:
            continue
    raise FileNotFoundError(
        "Failed to read prompt.md; expected adjacent to package or CWD."
    )


BASE_INSTRUCTIONS = read_base_instructions()


def read_prefix_content() -> str:
    candidates = [
        Path(__file__).parent.parent / "prefix.md",
        Path(__file__).parent / "prefix.md",
        Path(getattr(sys, "_MEIPASS", "")) / "prefix.md" if getattr(sys, "_MEIPASS", None) else None,
        Path.cwd() / "prefix.md",
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        except Exception:
            continue
    return ""  # Return empty string if prefix.md not found or empty


PREFIX_CONTENT = read_prefix_content()
