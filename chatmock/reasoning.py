from __future__ import annotations

from typing import Any, Dict

from .model_registry import DEFAULT_REASONING_EFFORTS, allowed_efforts_for_model, extract_reasoning_from_model_name


def build_reasoning_param(
    base_effort: str = "medium",
    base_summary: str = "auto",
    overrides: Dict[str, Any] | None = None,
    *,
    allowed_efforts: frozenset[str] | None = None,
) -> Dict[str, Any]:
    effort = (base_effort or "").strip().lower()
    summary = (base_summary or "").strip().lower()

    valid_efforts = allowed_efforts or DEFAULT_REASONING_EFFORTS
    valid_summaries = {"auto", "concise", "detailed", "none"}

    if isinstance(overrides, dict):
        o_eff = str(overrides.get("effort", "")).strip().lower()
        o_sum = str(overrides.get("summary", "")).strip().lower()
        if o_eff in valid_efforts and o_eff:
            effort = o_eff
        if o_sum in valid_summaries and o_sum:
            summary = o_sum
    if effort not in valid_efforts:
        effort = "medium"
    if summary not in valid_summaries:
        summary = "auto"

    reasoning: Dict[str, Any] = {"effort": effort}
    if summary != "none":
        reasoning["summary"] = summary
    return reasoning


def apply_reasoning_to_message(
    message: Dict[str, Any],
    reasoning_summary_text: str,
    reasoning_full_text: str,
    compat: str,
) -> Dict[str, Any]:
    try:
        compat = (compat or "think-tags").strip().lower()
    except Exception:
        compat = "think-tags"

    if compat == "o3":
        rtxt_parts: list[str] = []
        if isinstance(reasoning_summary_text, str) and reasoning_summary_text.strip():
            rtxt_parts.append(reasoning_summary_text)
        if isinstance(reasoning_full_text, str) and reasoning_full_text.strip():
            rtxt_parts.append(reasoning_full_text)
        rtxt = "\n\n".join([p for p in rtxt_parts if p])
        if rtxt:
            message["reasoning"] = {"content": [{"type": "text", "text": rtxt}]}
        return message

    if compat in ("legacy", "current"):
        if reasoning_summary_text:
            message["reasoning_summary"] = reasoning_summary_text
        if reasoning_full_text:
            message["reasoning"] = reasoning_full_text
        return message

    rtxt_parts: list[str] = []
    if isinstance(reasoning_summary_text, str) and reasoning_summary_text.strip():
        rtxt_parts.append(reasoning_summary_text)
    if isinstance(reasoning_full_text, str) and reasoning_full_text.strip():
        rtxt_parts.append(reasoning_full_text)
    rtxt = "\n\n".join([p for p in rtxt_parts if p])
    if rtxt:
        think_block = f"<think>{rtxt}</think>"
        content_text = message.get("content") or ""
        if isinstance(content_text, str):
            message["content"] = think_block + (content_text or "")
    return message
