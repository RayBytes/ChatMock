from __future__ import annotations

import unittest

from chatmock.fast_mode import parse_optional_bool, resolve_service_tier, supports_priority_service_tier


class FastModeTests(unittest.TestCase):
    def test_parse_optional_bool(self) -> None:
        self.assertTrue(parse_optional_bool(True))
        self.assertTrue(parse_optional_bool("true"))
        self.assertFalse(parse_optional_bool(False))
        self.assertFalse(parse_optional_bool("off"))
        self.assertIsNone(parse_optional_bool("maybe"))

    def test_priority_allowlist_uses_normalized_model_ids(self) -> None:
        self.assertTrue(supports_priority_service_tier("gpt5.4"))
        self.assertFalse(supports_priority_service_tier("gpt-5.3-codex"))

    def test_explicit_fast_mode_true_errors_for_unsupported_model(self) -> None:
        resolution = resolve_service_tier(
            "gpt-5.3-codex",
            request_fast_mode=True,
            server_fast_mode=False,
        )
        self.assertIsNone(resolution.service_tier)
        self.assertIsNotNone(resolution.error_message)

    def test_server_default_fast_mode_falls_back_on_unsupported_model(self) -> None:
        resolution = resolve_service_tier(
            "gpt-5.3-codex",
            server_fast_mode=True,
        )
        self.assertIsNone(resolution.service_tier)
        self.assertIsNone(resolution.error_message)
        self.assertIsNotNone(resolution.warning_message)

    def test_request_fast_mode_false_overrides_server_default(self) -> None:
        resolution = resolve_service_tier(
            "gpt-5.4",
            request_fast_mode=False,
            server_fast_mode=True,
        )
        self.assertIsNone(resolution.service_tier)
        self.assertIsNone(resolution.error_message)


if __name__ == "__main__":
    unittest.main()
