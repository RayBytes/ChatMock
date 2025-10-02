"""Common pytest fixtures for ChatMock test suite."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Ensure repository root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Do not disable external plugins; run with normal pytest plugin autoload.


@pytest.fixture
def temp_home_env(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated home dir and wire env vars ChatMock reads."""
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        # Both envs are consulted by utils.read_auth_file/get_home_dir
        monkeypatch.setenv("CHATGPT_LOCAL_HOME", str(base))
        monkeypatch.setenv("CODEX_HOME", str(base))
        yield base


@pytest.fixture
def flask_app() -> object:
    """Provide a Flask app; fail the test suite if Flask is missing."""
    try:
        from chatmock.app import create_app
    except ImportError:
        pytest.fail("Flask not available; tests requiring Flask must fail", pytrace=False)
    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(flask_app: object) -> object:
    """Flask test client."""
    return flask_app.test_client()
