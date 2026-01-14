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


def _read_prompt_with_fallback(filename: str, fallback: str) -> str:
    content = _read_prompt_text(filename)
    return content if isinstance(content, str) and content.strip() else fallback


BASE_INSTRUCTIONS = read_base_instructions()

# Model-specific instructions (from official Codex repo)
GPT5_CODEX_INSTRUCTIONS = _read_prompt_with_fallback("gpt_5_codex_prompt.md", BASE_INSTRUCTIONS)
GPT5_1_INSTRUCTIONS = _read_prompt_with_fallback("gpt_5_1_prompt.md", BASE_INSTRUCTIONS)
GPT5_2_INSTRUCTIONS = _read_prompt_with_fallback("gpt_5_2_prompt.md", BASE_INSTRUCTIONS)
GPT5_1_CODEX_MAX_INSTRUCTIONS = _read_prompt_with_fallback("gpt_5_1_codex_max_prompt.md", GPT5_CODEX_INSTRUCTIONS)

# Separator for concatenating IDE context to instructions (like Codex uses for AGENTS.md)
IDE_CONTEXT_SEPARATOR = "\n\n--- ide-context ---\n\n"


def get_instructions_for_model(model: str) -> str:
    """Get the appropriate base instructions for a given model."""
    model_lower = model.lower()

    # GPT-5.2 family
    if "gpt-5.2" in model_lower:
        return GPT5_2_INSTRUCTIONS

    # GPT-5.1-codex-max
    if "gpt-5.1-codex-max" in model_lower or "codex-max" in model_lower:
        return GPT5_1_CODEX_MAX_INSTRUCTIONS

    # GPT-5.1 family (non-codex)
    if "gpt-5.1" in model_lower and "codex" not in model_lower:
        return GPT5_1_INSTRUCTIONS

    # Codex models (gpt-5-codex, gpt-5.1-codex, codex-mini)
    if "codex" in model_lower:
        return GPT5_CODEX_INSTRUCTIONS

    # Default: BASE_INSTRUCTIONS
    return BASE_INSTRUCTIONS


# Known official prompt prefixes - if client sends these, don't prepend our own
OFFICIAL_PROMPT_PREFIXES = (
    "You are GPT-5",
    "You are GPT-4",
    "You are a coding agent running in the Codex CLI",
    "You are an AI assistant",
    "You are an AI coding agent",  # Cursor
    "You are Claude",  # Claude Code
    # Add more as needed
)


def has_official_instructions(instructions: str | None) -> bool:
    """Check if instructions already contain an official prompt.

    If client sends official instructions, we don't need to prepend our own
    (saves context tokens).
    """
    if not isinstance(instructions, str) or not instructions.strip():
        return False

    text = instructions.strip()
    for prefix in OFFICIAL_PROMPT_PREFIXES:
        if text.startswith(prefix):
            return True

    return False


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
        "id": "gpt-5.2-codex",
        "name": "GPT-5.2 Codex",
        "description": "Latest enhanced coding model with xhigh reasoning support",
        "capabilities": ["reasoning", "function_calling", "coding"],
        "efforts": ["xhigh", "high", "medium", "low"],
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
