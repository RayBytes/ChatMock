"""Tests for auth file utilities in chatmock.utils."""

from __future__ import annotations

import json
from pathlib import Path

from chatmock.utils import read_auth_file, write_auth_file


def test_read_auth_file_finds_in_env(temp_home_env: Path) -> None:
    data = {"OPENAI_API_KEY": "sk-xyz", "tokens": {"access_token": "a"}}
    auth_path = temp_home_env / "auth.json"
    auth_path.write_text(json.dumps(data), encoding="utf-8")
    loaded = read_auth_file()
    assert loaded == data


def test_write_auth_file_persists_json(temp_home_env: Path) -> None:
    data = {"OPENAI_API_KEY": "sk-abc", "tokens": {"id_token": "i"}}
    ok = write_auth_file(data)
    assert ok
    contents = json.loads((temp_home_env / "auth.json").read_text(encoding="utf-8"))
    assert contents == data
