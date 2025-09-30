"""Session and fingerprint helpers for grouping related requests."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from typing import Any

_LOCK = threading.Lock()
_FINGERPRINT_TO_UUID: dict[str, str] = {}
_ORDER: list[str] = []
_MAX_ENTRIES = 10000


def _canonicalize_first_user_message(  # noqa: C901
    input_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the first normalized user message from Responses input."""
    for item in input_items:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        role = item.get("role")
        if role != "user":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        norm_content = []
        for part in content:  # pragma: no branch
            if not isinstance(part, dict):  # pragma: no branch
                continue
            ptype = part.get("type")
            if ptype == "input_text":
                text = part.get("text") if isinstance(part.get("text"), str) else ""
                if text:
                    norm_content.append({"type": "input_text", "text": text})
            elif ptype == "input_image":  # pragma: no branch
                url = part.get("image_url") if isinstance(part.get("image_url"), str) else None
                if url:  # pragma: no branch
                    norm_content.append({"type": "input_image", "image_url": url})
        if norm_content:  # pragma: no branch
            return {"type": "message", "role": "user", "content": norm_content}
    return None


def canonicalize_prefix(instructions: str | None, input_items: list[dict[str, Any]]) -> str:
    """Build a stable JSON prefix from instructions and first user message."""
    prefix: dict[str, Any] = {}
    if isinstance(instructions, str) and instructions.strip():
        prefix["instructions"] = instructions.strip()
    first_user = _canonicalize_first_user_message(input_items)
    if first_user is not None:
        prefix["first_user_message"] = first_user
    return json.dumps(prefix, sort_keys=True, separators=(",", ":"))


def _fingerprint(s: str) -> str:
    """SHA-256 hex digest of the provided string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _remember(fp: str, sid: str) -> None:
    """Record a mapping and enforce a bounded cache size."""
    if fp in _FINGERPRINT_TO_UUID:
        return
    _FINGERPRINT_TO_UUID[fp] = sid
    _ORDER.append(fp)
    if len(_ORDER) > _MAX_ENTRIES:
        oldest = _ORDER.pop(0)
        _FINGERPRINT_TO_UUID.pop(oldest, None)


def ensure_session_id(
    instructions: str | None,
    input_items: list[dict[str, Any]],
    client_supplied: str | None = None,
) -> str:
    """Return client session id; derive from content when not provided."""
    if isinstance(client_supplied, str) and client_supplied.strip():
        return client_supplied.strip()

    canon = canonicalize_prefix(instructions, input_items)
    fp = _fingerprint(canon)
    with _LOCK:
        if fp in _FINGERPRINT_TO_UUID:
            return _FINGERPRINT_TO_UUID[fp]
        sid = str(uuid.uuid4())
        _remember(fp, sid)
        return sid
