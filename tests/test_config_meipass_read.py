"""Test _read_prompt_text reading from sys._MEIPASS candidate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from chatmock import config


def test__read_prompt_text_meipass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Create a fake _MEIPASS directory path string
    meipass = tmp_path / "bundle"
    meipass.mkdir()

    # Patch sys._MEIPASS so config._read_prompt_text includes this candidate
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    # Patch Path used in config so only the _MEIPASS candidate "exists"
    class _P:
        def __init__(self, p: str | None = "") -> None:
            self._p = str(p or "")

        def __truediv__(self, other: object) -> _P:
            return _P(self._p.rstrip("/") + "/" + str(other))

        @property
        def parent(self) -> _P:
            return self

        @staticmethod
        def cwd() -> _P:
            return _P("CWD")

        def exists(self) -> bool:
            p = self._p.replace("\\", "/")
            return p.endswith(str(meipass / "prompt.md").replace("\\", "/")) or p.endswith(
                str(meipass / "prompt_gpt5_codex.md").replace("\\", "/")
            )

        def read_text(self, encoding: str = "utf-8") -> str:
            if self._p.endswith("prompt.md"):
                return "BASE"
            if self._p.endswith("prompt_gpt5_codex.md"):
                return "CODEX"
            raise AssertionError("unexpected read_text path")

    monkeypatch.setattr(config, "Path", _P, raising=True)

    base = config._read_prompt_text("prompt.md")
    codex = config._read_prompt_text("prompt_gpt5_codex.md")
    assert base == "BASE" and codex == "CODEX"
