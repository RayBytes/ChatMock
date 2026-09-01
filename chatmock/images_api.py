from __future__ import annotations

from typing import Any, Dict, List

# Deliberately free of intra-package imports: utils.py imports this module, and
# model_catalog -> utils would close the cycle. SSE parsing lives in
# responses_api.py, which already owns it.


IMAGE_TOOL_TYPE = "image_generation"

# Model that orchestrates the call. The picture itself is always drawn by the
# backend's own image model, so the cheapest chat model does the job.
DEFAULT_IMAGE_ORCHESTRATOR_MODEL = "gpt-5.4-mini"

# Tool parameters the backend accepts today. 'n' shows up in the echoed tool
# config but is refused on input ("Unknown parameter: 'tools[0].n'"), so several
# images means several requests.
IMAGE_TOOL_PARAM_KEYS = (
    "size",
    "quality",
    "output_format",
    "output_compression",
    "background",
    "moderation",
)

MAX_IMAGES_PER_REQUEST = 4


def build_image_tool(params: Dict[str, Any] | None) -> Dict[str, Any]:
    tool: Dict[str, Any] = {"type": IMAGE_TOOL_TYPE}
    if isinstance(params, dict):
        for key in IMAGE_TOOL_PARAM_KEYS:
            value = params.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            tool[key] = value
    return tool


def size_hint_instruction(size: Any) -> str | None:
    """Turn a requested size into plain text.

    The backend ignores the `size` parameter (the echo always reads "auto") and
    picks the aspect ratio from the prompt, so the request only lands if it is
    written out for the model to read.
    """
    if not isinstance(size, str):
        return None
    raw = size.strip().lower()
    if not raw or raw == "auto" or "x" not in raw:
        return None
    left, _, right = raw.partition("x")
    try:
        width = int(left)
        height = int(right)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    if width == height:
        shape = "square (1:1)"
    elif width > height:
        shape = "landscape"
    else:
        shape = "portrait"
    return f"The image must be {shape}, as close as possible to {width}x{height} pixels."


def build_image_request_payload(
    prompt: str,
    *,
    model: str,
    tool_params: Dict[str, Any] | None = None,
    input_images: List[str] | None = None,
) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for url in input_images or []:
        if isinstance(url, str) and url.strip():
            content.append({"type": "input_image", "image_url": url})

    instructions = [
        "You generate images. Call the image tool exactly once with the user's "
        "request and write nothing else."
    ]
    hint = size_hint_instruction((tool_params or {}).get("size"))
    if hint:
        instructions.append(hint)

    return {
        "model": model,
        "instructions": " ".join(instructions),
        "input": [{"type": "message", "role": "user", "content": content}],
        "tools": [build_image_tool(tool_params)],
        "tool_choice": {"type": IMAGE_TOOL_TYPE},
        "parallel_tool_calls": False,
        "store": False,
        "stream": True,
    }


def image_item_to_openai(item: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"b64_json": item.get("result") or ""}
    revised = item.get("revised_prompt")
    if isinstance(revised, str) and revised.strip():
        out["revised_prompt"] = revised
    # Not part of the OpenAI schema, but the backend decides these on its own and
    # the caller has no other way to learn what it actually got.
    for key in ("size", "output_format", "quality", "background"):
        value = item.get(key)
        if value is not None:
            out[key] = value
    return out


def data_url_for_item(item: Dict[str, Any]) -> str | None:
    b64 = item.get("result")
    if not isinstance(b64, str) or not b64:
        return None
    fmt = item.get("output_format") if isinstance(item.get("output_format"), str) else "png"
    return f"data:image/{fmt};base64,{b64}"


def image_markdown_for_item(item: Dict[str, Any]) -> str:
    url = data_url_for_item(item)
    if not url:
        return ""
    alt = item.get("revised_prompt")
    alt = alt.replace("\n", " ").strip()[:120] if isinstance(alt, str) else ""
    return f"\n\n![{alt or 'image'}]({url})"


def usage_to_openai(usage: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(usage, dict):
        return None
    try:
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
    except (TypeError, ValueError):
        return None
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(usage.get("total_tokens") or (input_tokens + output_tokens)),
    }
