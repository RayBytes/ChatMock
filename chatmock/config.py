from __future__ import annotations

import os
import sys
from pathlib import Path
from .settings import load_config


_cfg = {}
try:
    _cfg = load_config(None)
except Exception:
    _cfg = {}

CLIENT_ID_DEFAULT = (
    (_cfg.get("oauth", {}) or {}).get("client_id")
    or os.getenv("CHATGPT_LOCAL_CLIENT_ID")
    or "app_EMoamEEZ73f0CkXaXp7hrann"
)

CHATGPT_RESPONSES_URL = (
    (_cfg.get("upstream", {}) or {}).get("responses_url")
    or "https://chatgpt.com/backend-api/codex/responses"
)


def read_base_instructions() -> str:
    # 0) Config override: instructions.path
    try:
        instr_cfg = (_cfg.get("instructions") or {}) if isinstance(_cfg, dict) else {}
        custom_path = instr_cfg.get("path") if isinstance(instr_cfg, dict) else None
        if isinstance(custom_path, str) and custom_path.strip():
            p = Path(custom_path).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            if p.exists():
                content = p.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
    except Exception:
        pass

    # 1) Default locations
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
