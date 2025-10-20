"""Cover read_auth_file invalid JSON and not found cases."""

from __future__ import annotations

import json
from pathlib import Path

from chatmock import utils


def test_read_auth_file_invalid_json(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    base = tmp_path
    (base / "auth.json").write_text("{not-json}", encoding="utf-8")
    monkeypatch.setenv("CHATGPT_LOCAL_HOME", str(base))
    monkeypatch.setenv("CODEX_HOME", str(base))
    # Provide a valid fallback at ~/.chatgpt-local/auth.json
    home_chatgpt = tmp_path / "home/.chatgpt-local"
    home_chatgpt.mkdir(parents=True, exist_ok=True)
    valid = {"OPENAI_API_KEY": "sk-test", "tokens": {"access_token": "a"}}
    (home_chatgpt / "auth.json").write_text(json.dumps(valid), encoding="utf-8")
    orig_path = utils.Path

    def _p(s: str):  # type: ignore[no-untyped-def]
        s = str(s).replace("~/.chatgpt-local", str(tmp_path / "home/.chatgpt-local"))
        s = s.replace("~/.codex", str(tmp_path / "home/.codex"))
        return orig_path(s)

    monkeypatch.setattr(utils, "Path", _p, raising=True)
    assert utils.read_auth_file() == valid


def test_read_auth_file_not_found(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    base = tmp_path / "nope"
    monkeypatch.setenv("CHATGPT_LOCAL_HOME", str(base))
    monkeypatch.setenv("CODEX_HOME", str(base))
    # Ensure no fallbacks exist
    orig_path = utils.Path

    def _p(s: str):  # type: ignore[no-untyped-def]
        s = str(s).replace("~/.chatgpt-local", str(tmp_path / "home/.chatgpt-local"))
        s = s.replace("~/.codex", str(tmp_path / "home/.codex"))
        return orig_path(s)

    monkeypatch.setattr(utils, "Path", _p, raising=True)
    assert utils.read_auth_file() is None
