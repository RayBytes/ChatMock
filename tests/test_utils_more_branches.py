"""Additional branch coverage for utils helpers."""

from __future__ import annotations

from pathlib import Path

from chatmock import utils


def test_write_auth_file_sets_mode_when_supported(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    # Ensure we write into a temp home dir
    monkeypatch.setattr(utils, "get_home_dir", lambda: str(tmp_path), raising=True)
    # Provide a stub for os.fchmod so the line executes without AttributeError
    monkeypatch.setattr(utils.os, "fchmod", lambda *_a, **_k: None, raising=False)
    ok = utils.write_auth_file({"tokens": {"x": 1}})
    assert ok
    assert (tmp_path / "auth.json").exists()


def test_convert_assistant_tool_calls_ignores_non_function_type() -> None:
    msgs = [
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "c1", "type": "nonfunc", "function": {"name": "x", "arguments": "{}"}}
            ],
        },
        {"role": "user", "content": "hi"},
    ]
    out = utils.convert_chat_messages_to_responses_input(msgs)
    # Ensure no function_call item was produced for non-function type
    assert not any(o.get("type") == "function_call" for o in out)
