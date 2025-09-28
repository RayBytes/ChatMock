"""Exercise CLI unknown command branch in main()."""

from __future__ import annotations

import types

import pytest

from chatmock import cli


def test_main_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    parser_cls = cli.argparse.ArgumentParser

    def fake_parse(self):  # type: ignore[no-untyped-def]
        return types.SimpleNamespace(command="unknown")

    monkeypatch.setattr(parser_cls, "parse_args", fake_parse, raising=True)
    with pytest.raises(SystemExit):
        cli.main()
