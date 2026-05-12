from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

from chatmock import cli


class CLIServeFlagTests(unittest.TestCase):
    def _run_main(self, argv: list[str], *, env: dict[str, str] | None = None) -> dict[str, object]:
        with patch.dict(os.environ, env or {}, clear=True):
            with patch.object(sys, "argv", argv):
                with patch("chatmock.cli.cmd_serve", return_value=0) as mock_cmd_serve:
                    with self.assertRaises(SystemExit) as exit_info:
                        cli.main()
        self.assertEqual(exit_info.exception.code, 0)
        return mock_cmd_serve.call_args.kwargs

    def test_serve_defaults_responses_websocket_upstream_disabled(self) -> None:
        kwargs = self._run_main(["chatmock", "serve"])
        self.assertFalse(kwargs["responses_websocket_upstream"])

    def test_serve_can_enable_responses_websocket_upstream(self) -> None:
        kwargs = self._run_main(["chatmock", "serve", "--responses-websocket-upstream"])
        self.assertTrue(kwargs["responses_websocket_upstream"])

    def test_serve_can_explicitly_disable_responses_websocket_upstream(self) -> None:
        kwargs = self._run_main(
            ["chatmock", "serve", "--no-responses-websocket-upstream"],
            env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM": "true"},
        )
        self.assertFalse(kwargs["responses_websocket_upstream"])

    def test_serve_uses_env_to_enable_responses_websocket_upstream(self) -> None:
        kwargs = self._run_main(
            ["chatmock", "serve"],
            env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM": "yes"},
        )
        self.assertTrue(kwargs["responses_websocket_upstream"])

    def test_serve_env_falsey_values_do_not_enable_responses_websocket_upstream(self) -> None:
        for env_value in ("false", "0"):
            with self.subTest(env_value=env_value):
                kwargs = self._run_main(
                    ["chatmock", "serve"],
                    env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM": env_value},
                )
                self.assertFalse(kwargs["responses_websocket_upstream"])

    def test_serve_defaults_responses_websocket_upstream_stateful_disabled(self) -> None:
        kwargs = self._run_main(["chatmock", "serve"])
        self.assertFalse(kwargs["responses_websocket_upstream_stateful"])

    def test_serve_can_enable_responses_websocket_upstream_stateful(self) -> None:
        kwargs = self._run_main(
            [
                "chatmock",
                "serve",
                "--responses-websocket-upstream",
                "--responses-websocket-upstream-stateful",
            ]
        )
        self.assertTrue(kwargs["responses_websocket_upstream"])
        self.assertTrue(kwargs["responses_websocket_upstream_stateful"])

    def test_serve_can_explicitly_disable_responses_websocket_upstream_stateful(self) -> None:
        kwargs = self._run_main(
            ["chatmock", "serve", "--no-responses-websocket-upstream-stateful"],
            env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM_STATEFUL": "true"},
        )
        self.assertFalse(kwargs["responses_websocket_upstream_stateful"])

    def test_serve_uses_env_to_enable_responses_websocket_upstream_stateful(self) -> None:
        kwargs = self._run_main(
            ["chatmock", "serve"],
            env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM_STATEFUL": "yes"},
        )
        self.assertTrue(kwargs["responses_websocket_upstream_stateful"])

    def test_serve_env_falsey_values_do_not_enable_responses_websocket_upstream_stateful(self) -> None:
        for env_value in ("false", "0"):
            with self.subTest(env_value=env_value):
                kwargs = self._run_main(
                    ["chatmock", "serve"],
                    env={"CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM_STATEFUL": env_value},
                )
                self.assertFalse(kwargs["responses_websocket_upstream_stateful"])
