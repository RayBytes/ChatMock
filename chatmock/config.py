from __future__ import annotations

import os
import sys
from pathlib import Path


CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_ISSUER_DEFAULT = os.getenv("CHATGPT_LOCAL_ISSUER") or "https://auth.openai.com"
OAUTH_TOKEN_URL = f"{OAUTH_ISSUER_DEFAULT}/oauth/token"

CHATGPT_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"


def _read_prompt_text(filename: str) -> str | None:
    candidates = [
        Path(__file__).parent.parent / filename,
        Path(__file__).parent / filename,
        Path(getattr(sys, "_MEIPASS", "")) / filename if getattr(sys, "_MEIPASS", None) else None,
        Path.cwd() / filename,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except Exception:
            continue
    return None


def read_base_instructions() -> str:
    content = _read_prompt_text("prompt.md")
    if content is None:
        raise FileNotFoundError("Failed to read prompt.md; expected adjacent to package or CWD.")
    return content


def read_gpt5_codex_instructions(fallback: str) -> str:
    content = _read_prompt_text("prompt_gpt5_codex.md")
    return content if isinstance(content, str) and content.strip() else fallback


BASE_INSTRUCTIONS = read_base_instructions()
GPT5_CODEX_INSTRUCTIONS = read_gpt5_codex_instructions(BASE_INSTRUCTIONS)


# Central model definitions - single source of truth
# Each model: (id, name, description, capabilities, efforts, experimental)
AVAILABLE_MODELS = [
    {
        "id": "gpt-5",
        "name": "GPT-5",
        "description": "Latest flagship model from OpenAI with advanced reasoning capabilities",
        "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
        "efforts": ["high", "medium", "low", "minimal"],
        "experimental": False,
    },
    {
        "id": "gpt-5.1",
        "name": "GPT-5.1",
        "description": "Enhanced version of GPT-5 with improved capabilities",
        "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
        "efforts": ["high", "medium", "low"],
        "experimental": False,
    },
    {
        "id": "gpt-5.2",
        "name": "GPT-5.2",
        "description": "Latest enhanced version with xhigh reasoning support",
        "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
        "efforts": ["xhigh", "high", "medium", "low"],
        "experimental": False,
    },
    {
        "id": "gpt-5-codex",
        "name": "GPT-5 Codex",
        "description": "Specialized model optimized for coding tasks",
        "capabilities": ["reasoning", "function_calling", "coding"],
        "efforts": ["high", "medium", "low"],
        "experimental": False,
    },
    {
        "id": "gpt-5.1-codex",
        "name": "GPT-5.1 Codex",
        "description": "Enhanced coding model with improved capabilities",
        "capabilities": ["reasoning", "function_calling", "coding"],
        "efforts": ["high", "medium", "low"],
        "experimental": False,
    },
    {
        "id": "gpt-5.1-codex-max",
        "name": "GPT-5.1 Codex Max",
        "description": "Maximum capability coding model with xhigh reasoning",
        "capabilities": ["reasoning", "function_calling", "coding"],
        "efforts": ["xhigh", "high", "medium", "low"],
        "experimental": False,
    },
    {
        "id": "gpt-5.1-codex-mini",
        "name": "GPT-5.1 Codex Mini",
        "description": "Lightweight enhanced coding model for faster responses",
        "capabilities": ["coding", "function_calling"],
        "efforts": [],
        "experimental": False,
    },
    {
        "id": "codex-mini",
        "name": "Codex Mini",
        "description": "Lightweight variant for faster coding responses",
        "capabilities": ["coding", "function_calling"],
        "efforts": [],
        "experimental": False,
    },
]


def get_model_ids(expose_reasoning_variants: bool = False, expose_experimental: bool = False) -> list[str]:
    """Get list of model IDs based on configuration."""
    model_ids = []
    for model in AVAILABLE_MODELS:
        if model.get("experimental", False) and not expose_experimental:
            continue
        model_ids.append(model["id"])
        if expose_reasoning_variants and model.get("efforts"):
            for effort in model["efforts"]:
                model_ids.append(f"{model['id']}-{effort}")
    return model_ids
