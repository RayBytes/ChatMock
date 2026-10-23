from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from chatmock.app import create_app
from chatmock.upstream import start_upstream_with_429_fallback


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(model_sync=False)
        self.catalog = SimpleNamespace(
            models=lambda: (
                SimpleNamespace(slug="gpt-reserve", supported_in_api=True),
            )
        )

    def test_disabled_fallback_preserves_429(self) -> None:
        calls: list[dict[str, object]] = []
        first = FakeResponse(429)

        def fake_raw(payload, **kwargs):
            calls.append(payload)
            return first, None

        with self.app.app_context(), patch("chatmock.upstream._start_upstream_raw_request", side_effect=fake_raw), patch(
            "chatmock.upstream.current_model_catalog", return_value=self.catalog
        ):
            result, error = start_upstream_with_429_fallback({"model": "gpt-5.6-luna", "input": []})

        self.assertIs(result, first)
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1)

    def test_enabled_fallback_retries_once_with_catalog_model(self) -> None:
        calls: list[dict[str, object]] = []
        first = FakeResponse(429)
        second = FakeResponse(200)

        def fake_raw(payload, **kwargs):
            calls.append(payload)
            return (first, None) if len(calls) == 1 else (second, None)

        self.app.config.update(FALLBACK_ON_429=True, FALLBACK_MODEL="gpt-reserve")
        with self.app.app_context(), patch("chatmock.upstream._start_upstream_raw_request", side_effect=fake_raw), patch(
            "chatmock.upstream.current_model_catalog", return_value=self.catalog
        ):
            result, error = start_upstream_with_429_fallback(
                {"model": "gpt-5.6-luna", "input": [], "service_tier": "priority"}
            )

        self.assertIs(result, second)
        self.assertIsNone(error)
        self.assertTrue(first.closed)
        self.assertEqual([call["model"] for call in calls], ["gpt-5.6-luna", "gpt-reserve"])
        self.assertNotIn("service_tier", calls[1])

    def test_fallback_model_must_be_catalog_supported(self) -> None:
        calls: list[dict[str, object]] = []
        first = FakeResponse(429)

        def fake_raw(payload, **kwargs):
            calls.append(payload)
            return first, None

        unsupported = SimpleNamespace(models=lambda: (SimpleNamespace(slug="gpt-reserve", supported_in_api=False),))
        self.app.config.update(FALLBACK_ON_429=True, FALLBACK_MODEL="gpt-reserve")
        with self.app.app_context(), patch("chatmock.upstream._start_upstream_raw_request", side_effect=fake_raw), patch(
            "chatmock.upstream.current_model_catalog", return_value=unsupported
        ):
            result, error = start_upstream_with_429_fallback({"model": "gpt-5.6-luna", "input": []})

        self.assertIs(result, first)
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
