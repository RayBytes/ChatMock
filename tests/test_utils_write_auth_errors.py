"""Exercise error branches in write_auth_file."""

from __future__ import annotations

from chatmock import utils


def test_write_auth_file_mkdir_fails(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(utils, "get_home_dir", lambda: str(tmp_path / "home"), raising=True)

    # Force mkdir to raise
    def _mkdir(self, *a, **k):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr(utils.Path, "mkdir", _mkdir, raising=True)
    ok = utils.write_auth_file({"tokens": {}})
    assert ok is False


def test_write_auth_file_open_fails(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(utils, "get_home_dir", lambda: str(tmp_path / "home2"), raising=True)
    # Allow mkdir, but make open fail
    monkeypatch.setattr(utils.Path, "mkdir", lambda self, *a, **k: None, raising=True)

    def _open(self, *a, **k):  # type: ignore[no-untyped-def]
        raise OSError("nope")

    monkeypatch.setattr(utils.Path, "open", _open, raising=True)
    ok = utils.write_auth_file({"tokens": {}})
    assert ok is False
