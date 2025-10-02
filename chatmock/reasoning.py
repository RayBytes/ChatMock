"""Helpers for building reasoning parameters and presentation."""

from __future__ import annotations

from typing import Any


def build_reasoning_param(
    base_effort: str = "medium", base_summary: str = "auto", overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a Responses API reasoning object from inputs and overrides."""
    effort = (base_effort or "").strip().lower()
    summary = (base_summary or "").strip().lower()

    valid_efforts = {"minimal", "low", "medium", "high"}
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

    reasoning: dict[str, Any] = {"effort": effort}
    if summary != "none":
        reasoning["summary"] = summary
    return reasoning


def apply_reasoning_to_message(  # noqa: C901
    message: dict[str, Any],
    reasoning_summary_text: str,
    reasoning_full_text: str,
    compat: str,
) -> dict[str, Any]:
    """Attach reasoning content/summary to a chat message based on compatibility mode."""
    compat = compat.strip().lower() if isinstance(compat, str) else "think-tags"

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

    ttxt_parts: list[str] = []
    if isinstance(reasoning_summary_text, str) and reasoning_summary_text.strip():
        ttxt_parts.append(reasoning_summary_text)
    if isinstance(reasoning_full_text, str) and reasoning_full_text.strip():
        ttxt_parts.append(reasoning_full_text)
    rtxt = "\n\n".join([p for p in ttxt_parts if p])
    if rtxt:
        think_block = f"<think>{rtxt}</think>"
        content_text = message.get("content") or ""
        if isinstance(content_text, str):
            message["content"] = think_block + (content_text or "")
    return message


def extract_reasoning_from_model_name(model: str | None) -> dict[str, Any] | None:  # noqa: PLR0911
    """Infer reasoning overrides from a model."""
    if not isinstance(model, str) or not model:
        return None
    s = model.strip().lower()
    if not s:
        return None
    efforts = {"minimal", "low", "medium", "high"}

    if ":" in s:
        maybe = s.rsplit(":", 1)[-1].strip()
        if maybe in efforts:
            return {"effort": maybe}

    for sep in ("-", "_"):
        if s.endswith(sep + "minimal"):
            return {"effort": "minimal"}
        if s.endswith(sep + "low"):
            return {"effort": "low"}
        if s.endswith(sep + "medium"):
            return {"effort": "medium"}
        if s.endswith(sep + "high"):
            return {"effort": "high"}

    return None
