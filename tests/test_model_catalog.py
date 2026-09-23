from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from chatmock.model_catalog import (
    CLIENT_VERSION_ENV,
    CODEX_MODELS_CLIENT_VERSION,
    CODEX_RELEASE_URL,
    CatalogModel,
    ModelCatalog,
)
from chatmock.app import create_app
from chatmock.fast_mode import supports_priority_service_tier


def response(payload: dict, status: int = 200) -> Mock:
    result = Mock()
    result.status_code = status
    result.json.return_value = payload
    result.headers = {}
    result.raise_for_status.side_effect = (
        requests.HTTPError("release unavailable") if status >= 400 else None
    )
    return result


class ModelCatalogTests(unittest.TestCase):
    def test_latest_stable_release_supplies_catalog_client_version(self) -> None:
        session = Mock()
        session.get.side_effect = [
            response({"tag_name": "rust-v0.157.0", "prerelease": False, "draft": False}),
            response({"models": [{"slug": "future-model", "visibility": "list"}]}),
        ]
        with tempfile.TemporaryDirectory() as directory:
            catalog = ModelCatalog(
                enabled=False, session=session, cache_path=Path(directory) / "models.json"
            )
            with patch("chatmock.model_catalog.get_effective_chatgpt_auth", return_value=("token", "account")):
                catalog._fetch_and_apply()

            self.assertEqual(session.get.call_args_list[0].args[0], CODEX_RELEASE_URL)
            self.assertEqual(session.get.call_args_list[1].kwargs["params"], {"client_version": "0.157.0"})
            self.assertEqual([model.slug for model in catalog.visible_models()], ["future-model"])

    def test_invalid_release_or_github_failure_uses_verified_fallback(self) -> None:
        for release in (
            response({"tag_name": "rust-v0.157.0-alpha.9", "prerelease": True}),
            response({"tag_name": "unrelated-v2.0.0", "prerelease": False}),
            response({}, 503),
        ):
            with self.subTest(release=release):
                session = Mock()
                session.get.return_value = release
                catalog = ModelCatalog(enabled=False, session=session)
                self.assertEqual(catalog._resolve_client_version(), CODEX_MODELS_CLIENT_VERSION)

    def test_environment_override_skips_github(self) -> None:
        session = Mock()
        with patch.dict("os.environ", {CLIENT_VERSION_ENV: "0.155.0"}):
            catalog = ModelCatalog(enabled=False, session=session)
        self.assertEqual(catalog._resolve_client_version(), "0.155.0")
        session.get.assert_not_called()

    def test_invalid_environment_override_fails_loudly(self) -> None:
        for version in ("latest", "0.157.0-alpha.9"):
            with self.subTest(version=version):
                with patch.dict("os.environ", {CLIENT_VERSION_ENV: version}):
                    with self.assertRaises(ValueError):
                        ModelCatalog(enabled=False)

    def test_cache_from_older_version_is_refreshed_without_losing_last_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "models.json"
            cache_path.write_text(
                json.dumps({
                    "account_id": "account",
                    "client_version": "0.146.0",
                    "fetched_at": "2026-09-23T00:00:00Z",
                    "models": [{"slug": "old-model", "visibility": "list"}],
                }),
                encoding="utf-8",
            )
            with patch("chatmock.model_catalog._account_id_from_auth_file", return_value="account"):
                catalog = ModelCatalog(cache_path=cache_path)
            self.assertEqual([model.slug for model in catalog._models], ["old-model"])
            self.assertIsNone(catalog._fetched_at)
            self.assertEqual(catalog._client_version, CODEX_MODELS_CLIENT_VERSION)

    def test_future_model_priority_uses_catalog_metadata(self) -> None:
        app = create_app(model_sync=False)
        catalog = app.extensions["chatmock_model_catalog"]
        catalog._models = (
            CatalogModel("future-model", ("low",), frozenset(("priority",)), 1, "list", True),
            CatalogModel("ordinary-model", ("low",), frozenset(), 2, "list", True),
        )
        with app.app_context():
            self.assertTrue(supports_priority_service_tier("future-model"))
            self.assertFalse(supports_priority_service_tier("ordinary-model"))
            self.assertIsNone(supports_priority_service_tier("unlisted-model"))


if __name__ == "__main__":
    unittest.main()
