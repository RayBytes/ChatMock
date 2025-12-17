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


# =============================================================================
# SMART INSTRUCTIONS DEBUG LOOP
# Enable via DEBUG_INSTRUCTIONS_BISECT=1
# This will iteratively remove tagged blocks to find which one causes
# "Instructions are not valid" error from upstream.
# =============================================================================

import re
from typing import List, Tuple, Callable


def _extract_tagged_blocks(text: str) -> List[Tuple[str, str, int, int]]:
    """Extract all tagged blocks from text.

    Returns list of (tag_name, full_match, start_pos, end_pos) tuples.
    Finds patterns like <tag_name>...</tag_name> including nested content.
    """
    # Match opening and closing tags with same name
    # Use non-greedy matching for content
    pattern = r'<([a-zA-Z_][a-zA-Z0-9_-]*)>(.*?)</\1>'
    blocks = []

    for match in re.finditer(pattern, text, re.DOTALL):
        tag_name = match.group(1)
        full_match = match.group(0)
        start = match.start()
        end = match.end()
        blocks.append((tag_name, full_match, start, end))

    return blocks


def _remove_block_by_index(text: str, blocks: List[Tuple[str, str, int, int]], idx: int) -> str:
    """Remove a specific block from text by index."""
    if idx < 0 or idx >= len(blocks):
        return text

    tag_name, full_match, start, end = blocks[idx]
    # Replace the block with nothing (remove it)
    return text[:start] + text[end:]


def debug_instructions_bisect(
    instructions: str,
    send_request_fn: Callable[[str], Tuple[int, str]],
    model: str = "unknown",
) -> Tuple[str | None, Path | None]:
    """Smart debug loop to find problematic tagged block in instructions.

    USAGE: Enable via DEBUG_INSTRUCTIONS_BISECT=1 environment variable.

    Algorithm:
    1. Send full instructions to upstream
    2. If 400 "instructions" error - remove one tagged block
    3. Repeat until success or no more blocks
    4. Write report showing removal order and final culprit

    Args:
        instructions: Full instructions string with tagged blocks
        send_request_fn: Function that sends request and returns (status_code, error_message)
                        Should return (200, "") on success, (400, "error text") on failure
        model: Model name for the report

    Returns:
        Tuple of (working_instructions or None, report_path or None)
    """
    env_val = os.getenv("DEBUG_INSTRUCTIONS_BISECT", "").lower()
    if env_val not in ("1", "true", "yes", "on"):
        return None, None

    print("[debug_bisect] Starting smart instructions debug loop...")

    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Extract all tagged blocks
    all_blocks = _extract_tagged_blocks(instructions)
    print(f"[debug_bisect] Found {len(all_blocks)} tagged blocks in instructions")

    if not all_blocks:
        print("[debug_bisect] No tagged blocks found, cannot bisect")
        return None, None

    # Log all found blocks
    for i, (tag_name, _, start, end) in enumerate(all_blocks):
        print(f"[debug_bisect]   [{i}] <{tag_name}> (chars {start}-{end}, len={end-start})")

    # Track removal history
    removal_history: List[Dict[str, Any]] = []
    current_instructions = instructions

    iteration = 0
    max_iterations = len(all_blocks) + 5  # Safety limit

    while iteration < max_iterations:
        iteration += 1
        print(f"\n[debug_bisect] === Iteration {iteration} ===")
        print(f"[debug_bisect] Current instructions length: {len(current_instructions)} chars")

        # Try sending request
        status_code, error_msg = send_request_fn(current_instructions)

        print(f"[debug_bisect] Response: status={status_code}, error={error_msg[:100] if error_msg else 'none'}...")

        if status_code < 400:
            # Success! We found the working version
            print(f"[debug_bisect] SUCCESS! Upstream accepted instructions")
            break

        # Check if it's an instructions error
        is_instructions_error = (
            status_code == 400 and
            error_msg and
            ("instructions" in error_msg.lower() or "invalid" in error_msg.lower())
        )

        if not is_instructions_error:
            print(f"[debug_bisect] Non-instructions error, stopping: {error_msg}")
            removal_history.append({
                "iteration": iteration,
                "action": "stopped",
                "reason": f"Non-instructions error: {error_msg}",
                "status_code": status_code,
            })
            break

        # Recalculate blocks from current instructions
        current_blocks = _extract_tagged_blocks(current_instructions)

        if not current_blocks:
            print("[debug_bisect] No more blocks to remove, but still failing")
            removal_history.append({
                "iteration": iteration,
                "action": "exhausted",
                "reason": "No more tagged blocks but still getting error",
                "error": error_msg,
            })
            break

        # Strategy: remove largest block first (more likely to be problematic)
        block_sizes = [(i, end - start) for i, (_, _, start, end) in enumerate(current_blocks)]
        block_sizes.sort(key=lambda x: x[1], reverse=True)

        block_to_remove = block_sizes[0][0]
        tag_name, full_match, start, end = current_blocks[block_to_remove]

        print(f"[debug_bisect] Removing block [{block_to_remove}]: <{tag_name}> ({end-start} chars)")

        removal_history.append({
            "iteration": iteration,
            "action": "removed",
            "block_index": block_to_remove,
            "tag_name": tag_name,
            "block_size": end - start,
            "block_preview": full_match[:200] + "..." if len(full_match) > 200 else full_match,
            "error_before": error_msg,
            "instructions_length_before": len(current_instructions),
        })

        # Remove the block
        current_instructions = _remove_block_by_index(current_instructions, current_blocks, block_to_remove)
        removal_history[-1]["instructions_length_after"] = len(current_instructions)

    # Generate report
    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "model": model,
        "original_instructions_length": len(instructions),
        "final_instructions_length": len(current_instructions),
        "total_blocks_found": len(all_blocks),
        "blocks_removed": len([h for h in removal_history if h.get("action") == "removed"]),
        "success": iteration < max_iterations and (not removal_history or removal_history[-1].get("action") != "exhausted"),
        "iterations": iteration,
        "all_blocks": [
            {"index": i, "tag": tag, "start": s, "end": e, "size": e - s}
            for i, (tag, _, s, e) in enumerate(all_blocks)
        ],
        "removal_history": removal_history,
    }

    # Identify the likely culprit (last removed block that made it work)
    if report["success"] and removal_history:
        last_removed = [h for h in removal_history if h.get("action") == "removed"]
        if last_removed:
            report["likely_culprit"] = last_removed[-1]
            print(f"\n[debug_bisect] LIKELY CULPRIT: <{last_removed[-1]['tag_name']}>")

    # Write report
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = data_dir / f"debug_instructions_bisect_{ts}.json"

    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[debug_bisect] Report written to: {report_file}")
    except Exception as e:
        print(f"[debug_bisect] Failed to write report: {e}")
        report_file = None

    # Also write the working instructions if we found them
    if report["success"]:
        working_file = data_dir / f"debug_instructions_working_{ts}.txt"
        try:
            with open(working_file, "w", encoding="utf-8") as f:
                f.write(current_instructions)
            print(f"[debug_bisect] Working instructions written to: {working_file}")
        except Exception as e:
            print(f"[debug_bisect] Failed to write working instructions: {e}")

    return current_instructions if report["success"] else None, report_file
