"""Test get_home_dir default path when env vars are unset."""

from __future__ import annotations

from chatmock.utils import get_home_dir


def test_get_home_dir_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("CHATGPT_LOCAL_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    path = get_home_dir()
    assert path.replace("\\", "/").endswith("/.chatgpt-local")
