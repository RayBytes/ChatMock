from __future__ import annotations

import json
from typing import Any, Dict, List
from tqdm import tqdm


def to_data_url(image_str: str) -> str:
    if not isinstance(image_str, str) or not image_str:
        return image_str
    s = image_str.strip()
    if s.startswith("data:image/"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    b64 = s.replace("\n", "").replace("\r", "")
    kind = "image/png"
    if b64.startswith("/9j/"):
        kind = "image/jpeg"
    elif b64.startswith("iVBORw0KGgo"):
        kind = "image/png"
    elif b64.startswith("R0lGOD"):
        kind = "image/gif"
    return f"data:{kind};base64,{b64}"


def convert_ollama_messages(
    messages: List[Dict[str, Any]] | None, top_images: List[str] | None
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    msgs = messages if isinstance(messages, list) else []
    pending_call_ids: List[str] = []
    call_counter = 0
    for m in tqdm(msgs, desc="Processing messages", unit="msg"):
        if not isinstance(m, dict):
            continue
        role = m.get("role") or "user"
        nm: Dict[str, Any] = {"role": role}

        content = m.get("content")
        images = m.get("images") if isinstance(m.get("images"), list) else []
        parts: List[Dict[str, Any]] = []
        if isinstance(content, list):
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text" and isinstance(p.get("text"), str):
                    parts.append({"type": "text", "text": p.get("text")})
        elif isinstance(content, str):
            parts.append({"type": "text", "text": content})
        for img in images:
            url = to_data_url(img)
            if isinstance(url, str) and url:
                parts.append({"type": "image_url", "image_url": {"url": url}})
        if parts:
            nm["content"] = parts

        if role == "assistant" and isinstance(m.get("tool_calls"), list):
            tcs = []
            for tc in m.get("tool_calls"):
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                name = fn.get("name") if isinstance(fn.get("name"), str) else None
                args = fn.get("arguments")
                if name is None:
                    continue
                call_id = tc.get("id") or tc.get("call_id")
                if not isinstance(call_id, str) or not call_id:
                    call_counter += 1
                    call_id = f"ollama_call_{call_counter}"
                pending_call_ids.append(call_id)
                tcs.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": args if isinstance(args, str) else (json.dumps(args) if isinstance(args, dict) else "{}"),
                        },
                    }
                )
            if tcs:
                nm["tool_calls"] = tcs

        if role == "tool":
            tci = m.get("tool_call_id") or m.get("id")
            if not isinstance(tci, str) or not tci:
                if pending_call_ids:
                    tci = pending_call_ids.pop(0)
            if isinstance(tci, str) and tci:
                nm["tool_call_id"] = tci

            if not parts and isinstance(content, str):
                nm["content"] = content

        out.append(nm)

    if isinstance(top_images, list) and top_images:
        attach_to = None
        for i in range(len(out) - 1, -1, -1):
            if out[i].get("role") == "user":
                attach_to = out[i]
                break
        if attach_to is None:
            attach_to = {"role": "user", "content": []}
            out.append(attach_to)
        attach_to.setdefault("content", [])
        for img in top_images:
            url = to_data_url(img)
            if isinstance(url, str) and url:
                attach_to["content"].append({"type": "image_url", "image_url": {"url": url}})
    return out


def normalize_ollama_tools(tools: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(tools, list):
        return out
    for t in tools:
        if not isinstance(t, dict):
            continue
        if isinstance(t.get("function"), dict):
            fn = t.get("function")
            name = fn.get("name") if isinstance(fn.get("name"), str) else None
            if not name:
                continue
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": fn.get("description") or "",
                        "parameters": fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {"type": "object", "properties": {}},
                    },
                }
            )
            continue
        name = t.get("name") if isinstance(t.get("name"), str) else None
        if name:
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": t.get("description") or "",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            )
    return out

