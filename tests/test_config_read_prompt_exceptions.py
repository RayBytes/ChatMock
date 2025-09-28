"""Exercise _read_prompt_text exception path in config."""

from __future__ import annotations

from chatmock import config


def test__read_prompt_text_handles_read_errors(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Force Path.exists True and Path.read_text to raise
    class _P:
        def __init__(self, *a, **k):  # type: ignore[no-untyped-def]
            pass

        def __truediv__(self, other):  # type: ignore[no-untyped-def]
            return self

        @property
        def parent(self):  # type: ignore[no-untyped-def]
            return self

        @staticmethod
        def cwd():  # type: ignore[no-untyped-def]
            return _P()

        def exists(self):  # type: ignore[no-untyped-def]
            return True

        def read_text(self, encoding="utf-8"):  # type: ignore[no-untyped-def]
            raise OSError("boom")

    monkeypatch.setattr(config, "Path", _P, raising=True)
    out = config._read_prompt_text("prompt.md")
    assert out is None
