#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any, Dict

import requests


def _post(url: str, api_key: str, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Session-Id": session_id,
        },
        json=payload,
        timeout=180,
    )
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    if response.status_code >= 400:
        raise RuntimeError(
            f"POST {url} failed with {response.status_code}: {json.dumps(body, ensure_ascii=False)}"
        )
    if not isinstance(body, dict):
        raise RuntimeError(f"Expected JSON object response, got: {body!r}")
    return body


def _usage_summary(body: Dict[str, Any]) -> Dict[str, Any]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return {}
    return usage


def _cached_tokens(body: Dict[str, Any]) -> int | None:
    usage = _usage_summary(body)
    details = usage.get("input_tokens_details")
    if not isinstance(details, dict):
        return None
    value = details.get("cached_tokens")
    try:
        return int(value)
    except Exception:
        return None


def _assistant_message_item(body: Dict[str, Any]) -> Dict[str, Any]:
    output = body.get("output")
    if not isinstance(output, list):
        raise RuntimeError("Response did not include an output list.")
    for item in output:
        if isinstance(item, dict) and item.get("type") == "message" and item.get("role") == "assistant":
            return item
    raise RuntimeError("Response did not include an assistant message item.")


def _user_message(text: str) -> Dict[str, Any]:
    return {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


def _default_prefix() -> str:
    seed = "Cache test prefix. Repeat this context exactly for cache measurement. "
    return "".join(seed for _ in range(220))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Drive two raw /v1/responses turns through ChatMock and check cached input tokens."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="ChatMock base URL.")
    parser.add_argument("--api-key", default="key", help="Bearer token to send to ChatMock.")
    parser.add_argument("--model", default="gpt-5.4", help="Model to request.")
    parser.add_argument(
        "--session-id",
        default=f"cache-check-{uuid.uuid4()}",
        help="Fixed X-Session-Id for both turns.",
    )
    parser.add_argument(
        "--prefix",
        default=_default_prefix(),
        help="Large repeated first-turn prompt prefix.",
    )
    parser.add_argument(
        "--first-question",
        default="Reply with exactly: alpha",
        help="Trailing instruction for the first turn.",
    )
    parser.add_argument(
        "--second-question",
        default="Reply with exactly: beta",
        help="Trailing instruction for the second turn.",
    )
    args = parser.parse_args()

    responses_url = args.base_url.rstrip("/") + "/v1/responses"
    session_id = args.session_id
    first_text = f"{args.prefix}\n\n{args.first_question}"
    second_text = args.second_question

    print(f"Using session id: {session_id}")
    print(f"POST target: {responses_url}")
    print("This checks the raw Responses usage object returned through ChatMock.")
    print()

    first_payload = {
        "model": args.model,
        "store": False,
        "stream": False,
        "input": first_text,
    }
    first_response = _post(responses_url, args.api_key, session_id, first_payload)
    assistant_item = _assistant_message_item(first_response)

    second_payload = {
        "model": args.model,
        "store": False,
        "stream": False,
        "input": [
            _user_message(first_text),
            assistant_item,
            _user_message(second_text),
        ],
    }
    second_response = _post(responses_url, args.api_key, session_id, second_payload)

    first_usage = _usage_summary(first_response)
    second_usage = _usage_summary(second_response)
    first_cached = _cached_tokens(first_response)
    second_cached = _cached_tokens(second_response)

    print("Turn 1")
    print(json.dumps(first_usage, indent=2, ensure_ascii=False) if first_usage else "  no usage object")
    print()
    print("Turn 2")
    print(json.dumps(second_usage, indent=2, ensure_ascii=False) if second_usage else "  no usage object")
    print()

    if second_cached is None:
        first_input_tokens = first_usage.get("input_tokens") if isinstance(first_usage, dict) else None
        second_input_tokens = second_usage.get("input_tokens") if isinstance(second_usage, dict) else None
        print("Result: inconclusive")
        print("Reason: upstream did not include `usage.input_tokens_details.cached_tokens`.")
        if isinstance(first_input_tokens, int) and isinstance(second_input_tokens, int):
            print(f"Observed input_tokens delta: first={first_input_tokens}, second={second_input_tokens}")
        print("Codex treats cached-token reporting as the direct cache-hit signal; without it, this script cannot prove caching.")
        return 2

    if second_cached > 0:
        print(f"Result: success, follow-up turn reported cached_tokens={second_cached}.")
        return 0

    print("Result: failure, follow-up turn reported cached_tokens=0.")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
