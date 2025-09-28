"""Configuration and prompt text loading for ChatMock."""

from __future__ import annotations

import os
import sys
from pathlib import Path

CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_ISSUER_DEFAULT = os.getenv("CHATGPT_LOCAL_ISSUER") or "https://auth.openai.com"
OAUTH_TOKEN_URL = f"{OAUTH_ISSUER_DEFAULT}/oauth/token"

CHATGPT_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"


def _read_prompt_text(filename: str) -> str | None:
    """Search common locations for the given prompt file and return its text."""
    candidates = [
        c
        for c in [
            Path(__file__).parent.parent / filename,
            Path(__file__).parent / filename,
            (Path(getattr(sys, "_MEIPASS", "")) / filename)
            if getattr(sys, "_MEIPASS", None)
            else None,
            Path.cwd() / filename,
        ]
        if c
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except (OSError, UnicodeDecodeError, ValueError) as exc:  # log and continue
            sys.stderr.write(f"[config] failed reading {candidate}: {exc}\n")
            continue
    return None


def read_base_instructions() -> str:
    """Load base instructions from prompt.md or raise if not found."""
    content = _read_prompt_text("prompt.md")
    if content is None:
        msg = "Failed to read prompt.md; expected adjacent to package or CWD."
        raise FileNotFoundError(msg)
    return content


def read_gpt5_codex_instructions(fallback: str) -> str:
    """Load GPT-5 Codex prompt text or return the provided fallback."""
    content = _read_prompt_text("prompt_gpt5_codex.md")
    return content if isinstance(content, str) and content.strip() else fallback


BASE_INSTRUCTIONS = read_base_instructions()
GPT5_CODEX_INSTRUCTIONS = read_gpt5_codex_instructions(BASE_INSTRUCTIONS)
