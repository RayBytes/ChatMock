#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any, Dict, Tuple

from websockets.sync.client import connect


def _user_message(text: str) -> Dict[str, Any]:
    return {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


def _receive_turn(ws) -> Tuple[str, Dict[str, Any]]:
    response_id: str | None = None
    assistant_item: Dict[str, Any] | None = None

    while True:
        raw = ws.recv(timeout=120)
        event = json.loads(raw)
        event_type = event.get("type")
        if event_type == "error":
            raise RuntimeError(f"websocket error: {json.dumps(event, ensure_ascii=False)}")
        if event_type == "response.created":
            response = event.get("response")
            if isinstance(response, dict) and isinstance(response.get("id"), str):
                response_id = response["id"]
        elif event_type == "response.output_item.done":
            item = event.get("item")
            if (
                isinstance(item, dict)
                and item.get("type") == "message"
                and item.get("role") == "assistant"
            ):
                assistant_item = item
        elif event_type == "response.completed":
            if not response_id:
                response = event.get("response")
                if isinstance(response, dict) and isinstance(response.get("id"), str):
                    response_id = response["id"]
            if not response_id:
                raise RuntimeError("turn completed without a response id")
            if assistant_item is None:
                raise RuntimeError("turn completed without an assistant message item")
            return response_id, assistant_item


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise ChatMock websocket reuse the same way Codex does."
    )
    parser.add_argument(
        "--ws-url",
        default="ws://127.0.0.1:8000/v1/responses",
        help="ChatMock websocket URL.",
    )
    parser.add_argument("--model", default="gpt-5.4", help="Model to request.")
    parser.add_argument(
        "--session-id",
        default=f"reuse-demo-{uuid.uuid4()}",
        help="Fixed X-Session-Id for the whole run.",
    )
    parser.add_argument(
        "--first-prompt",
        default="Say exactly: alpha",
        help="Prompt for the first turn.",
    )
    parser.add_argument(
        "--second-prompt",
        default="Now say exactly: beta",
        help="Prompt appended in the reuse-candidate turn.",
    )
    parser.add_argument(
        "--no-fast-mode",
        action="store_true",
        help="Do not send fast_mode=true.",
    )
    args = parser.parse_args()

    headers = {"X-Session-Id": args.session_id}
    fast_mode = not args.no_fast_mode

    print(f"Using websocket session id: {args.session_id}")
    print(f"Connecting to: {args.ws_url}")
    print("Run ChatMock with `python3 chatmock.py serve --verbose` in another terminal.")
    print("This verifies the Codex-aligned path: websocket `response.create` reuse.")
    print("HTTP `/v1/responses` is not expected to send `previous_response_id`.")
    print()

    with connect(args.ws_url, additional_headers=headers, open_timeout=15) as ws:
        first_request = {
            "type": "response.create",
            "model": args.model,
            "store": False,
            "input": args.first_prompt,
            "fast_mode": fast_mode,
        }
        ws.send(json.dumps(first_request))
        first_response_id, assistant_item = _receive_turn(ws)

        second_request = {
            "type": "response.create",
            "model": args.model,
            "store": False,
            "input": [
                _user_message(args.first_prompt),
                assistant_item,
                _user_message(args.second_prompt),
            ],
            "fast_mode": fast_mode,
        }
        ws.send(json.dumps(second_request))
        second_response_id, _ = _receive_turn(ws)

    print("Turn 1 completed.")
    print(f"  response id: {first_response_id}")
    print("Turn 2 completed.")
    print(f"  response id: {second_response_id}")
    print()
    print("Expected in the verbose ChatMock server log for turn 2:")
    print("  - outbound websocket payload includes `previous_response_id`")
    print("  - `previous_response_id` equals the first response id")
    print("  - outbound `input` only contains the new trailing user message")
    print()
    print("If turn 2 still shows the full conversation in the outbound websocket payload, reuse is not working.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
