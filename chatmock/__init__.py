"""
Public package API exports for ChatMock.

Avoid importing heavy submodules (e.g., Flask app) at import time to keep
lightweight modules importable without optional dependencies. Use lazy
attribute resolution for top-level symbols.
"""

from __future__ import annotations

import importlib

__all__ = ["create_app", "main"]


def __getattr__(name: str) -> object:  # pragma: no cover - simple import proxy
    if name == "create_app":
        return importlib.import_module(".app", __package__).create_app
    if name == "main":
        return importlib.import_module(".cli", __package__).main
    raise AttributeError(name)
