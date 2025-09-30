"""Test verbose logging callback in sse_translate_chat for web_search events."""

from __future__ import annotations

from chatmock.utils import sse_translate_chat


class _Up:
    def iter_lines(self, decode_unicode: bool = False):  # type: ignore[no-untyped-def]
        yield (
            b'data: {"type": "web_search_call.delta", "item_id": "ws1", '
            b'"item": {"parameters": {"q": "x"}}, "response": {"id": "r"}}'
        )
        yield (
            b'data: {"type": "web_search_call.completed", '
            b'"item_id": "ws1", "response": {"id": "r"}}'
        )
        yield b'data: {"type": "response.completed", "response": {}}'

    def close(self) -> None:
        return None


def test_sse_chat_vlog_called_for_web_search() -> None:
    logs: list[str] = []

    def vlog(line: str) -> None:
        logs.append(line)

    out = b"".join(sse_translate_chat(_Up(), "gpt-5", 1, verbose=True, vlog=vlog))
    assert logs
    assert any("CM_TOOLS" in log_line for log_line in logs)
    assert b"data: [DONE]" in out
