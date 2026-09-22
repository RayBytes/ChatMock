from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chatmock.model_catalog import CODEX_MODELS_CLIENT_VERSION, ModelCatalog


class ModelCatalogCacheTests(unittest.TestCase):
    def test_cache_from_older_client_version_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "models.json"
            payload = {
                "account_id": "test-account",
                "client_version": "0.146.0",
                "fetched_at": "2026-09-22T00:00:00Z",
                "models": [{"slug": "gpt-5.6-sol", "visibility": "list"}],
            }
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch("chatmock.model_catalog._account_id_from_auth_file", return_value="test-account"):
                old_catalog = ModelCatalog(cache_path=cache_path)
                self.assertEqual(old_catalog._models, ())

                payload["client_version"] = CODEX_MODELS_CLIENT_VERSION
                cache_path.write_text(json.dumps(payload), encoding="utf-8")
                current_catalog = ModelCatalog(cache_path=cache_path)
                self.assertEqual([model.slug for model in current_catalog._models], ["gpt-5.6-sol"])


if __name__ == "__main__":
    unittest.main()