"""Helper utilities for tests (fakes/mocks)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class FakeUpstream:
    """
    Minimal upstream stream emulator for SSE tests.

    Provide an iterable of text lines (without newlines). The iterator yields
    bytes lines as `iter_lines(decode_unicode=False)` like `requests` does.
    """

    def __init__(self, lines: Iterable[str], status_code: int = 200) -> None:
        """Initialize with a list of lines and a status code."""
        self._lines = list(lines)
        self.status_code = status_code
        self.text = ""  # populated when needed by tests
        self.content = b""  # ditto

    def iter_lines(self, *, decode_unicode: bool = False) -> Iterator[bytes]:
        """Yield bytes lines similarly to `requests.Response.iter_lines`."""
        # keep the signature parity, even if unused in tests
        _ = decode_unicode
        for line in self._lines:
            data = (line + "\n").encode("utf-8")
            yield data

    def close(self) -> None:  # parity with requests.Response
        """No-op close to mirror requests interface."""
