"""Unified debug logging for ChatMock.

Saves request/response payloads to JSON files in the data directory
for debugging purposes. Enabled via DEBUG_LOG=true environment variable.

Files are saved to CHATGPT_LOCAL_HOME directory (same as other data).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .utils import get_home_dir


def _get_data_dir() -> Path:
    """Get data directory path (same as other ChatMock data)."""
    return Path(get_home_dir())


def _is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    for var in ("DEBUG_LOG", "CHATGPT_LOCAL_DEBUG", "CHATGPT_LOCAL_DEBUG_LOG"):
        val = os.getenv(var, "").lower()
        if val in ("1", "true", "yes", "on"):
            return True
    return False


def dump_request(
    endpoint: str,
    incoming: Dict[str, Any],
    outgoing: Dict[str, Any] | None = None,
    *,
    extra: Dict[str, Any] | None = None,
) -> Path | None:
    """Dump request payloads to JSON file.

    Args:
        endpoint: API endpoint name (e.g., "chat_completions", "responses")
        incoming: Raw incoming request payload from client
        outgoing: Transformed payload sent to upstream (optional)
        extra: Additional debug info (optional)

    Returns:
        Path to the dump file, or None if debug is disabled
    """
    if not _is_debug_enabled():
        return None

    try:
        data_dir = _get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize endpoint name for filename
        safe_endpoint = endpoint.replace("/", "_").replace("\\", "_").strip("_")

        dump = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint,
            "incoming": incoming,
        }
        if outgoing is not None:
            dump["outgoing"] = outgoing
        if extra is not None:
            dump["extra"] = extra

        # Write to "last" file (overwritten each time)
        last_file = data_dir / f"debug_{safe_endpoint}.json"
        with open(last_file, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, ensure_ascii=False)

        return last_file
    except Exception as e:
        try:
            print(f"[debug] Failed to dump request: {e}")
        except Exception:
            pass
        return None


def dump_prompt(
    label: str,
    content: str,
    *,
    prefix: str = "prompt",
) -> Path | None:
    """Dump prompt/instructions to text file for debugging.

    Enabled via DEBUG_LOG_PROMPTS=1 (separate from DEBUG_LOG).

    Args:
        label: Description of the prompt (e.g., "cursor_system", "chatmock_instructions")
        content: The prompt content
        prefix: File prefix (default: "prompt")

    Returns:
        Path to the dump file, or None if disabled
    """
    env_val = os.getenv("DEBUG_LOG_PROMPTS", "").lower()
    if env_val not in ("1", "true", "yes", "on"):
        return None

    try:
        data_dir = _get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        # Include timestamp to distinguish multiple chats
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_label = label.replace("/", "_").replace("\\", "_").replace(" ", "_").strip("_")
        filename = f"debug_{prefix}_{safe_label}_{ts}.txt"

        filepath = data_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== {label} ===\n")
            f.write(f"Timestamp: {datetime.utcnow().isoformat()}Z\n\n")
            f.write(content)

        print(f"[debug] Wrote {len(content)} chars to {filepath}")
        return filepath
    except Exception as e:
        try:
            print(f"[debug] Failed to dump prompt: {e}")
        except Exception:
            pass
        return None


def dump_tools_debug(
    endpoint: str,
    raw_tools: Any,
    converted_tools: Any,
) -> Path | None:
    """Dump tools conversion debug info.

    Args:
        endpoint: API endpoint name
        raw_tools: Raw tools from incoming request
        converted_tools: Tools after conversion

    Returns:
        Path to the dump file, or None if debug is disabled
    """
    if not _is_debug_enabled():
        return None

    try:
        data_dir = _get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)

        safe_endpoint = endpoint.replace("/", "_").replace("\\", "_").strip("_")

        dump = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint,
            "raw_tools_count": len(raw_tools) if isinstance(raw_tools, list) else 0,
            "raw_tools": raw_tools,
            "converted_tools_count": len(converted_tools) if isinstance(converted_tools, list) else 0,
            "converted_tools": converted_tools,
        }

        tools_file = data_dir / f"debug_{safe_endpoint}_tools.json"
        with open(tools_file, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2, ensure_ascii=False)

        return tools_file
    except Exception as e:
        try:
            print(f"[debug] Failed to dump tools: {e}")
        except Exception:
            pass
        return None
