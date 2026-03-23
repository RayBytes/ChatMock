from __future__ import annotations

import unittest

from chatmock.model_registry import allowed_efforts_for_model, list_public_models, normalize_model_name


class ModelRegistryTests(unittest.TestCase):
    def test_normalizes_aliases(self) -> None:
        self.assertEqual(normalize_model_name("gpt5"), "gpt-5")
        self.assertEqual(normalize_model_name("gpt5.4"), "gpt-5.4")
        self.assertEqual(normalize_model_name("gpt5.4-mini"), "gpt-5.4-mini")
        self.assertEqual(normalize_model_name("gpt5.3-codex-spark"), "gpt-5.3-codex-spark")
        self.assertEqual(normalize_model_name("codex"), "codex-mini-latest")

    def test_strips_reasoning_suffixes(self) -> None:
        self.assertEqual(normalize_model_name("gpt-5.4-high"), "gpt-5.4")
        self.assertEqual(normalize_model_name("gpt-5.4-mini-high"), "gpt-5.4-mini")
        self.assertEqual(normalize_model_name("gpt-5.2_codemirror"), "gpt-5.2_codemirror")
        self.assertEqual(normalize_model_name("gpt-5.1-codex:max"), "gpt-5.1-codex:max")
        self.assertEqual(normalize_model_name("gpt-5.1-codex:high"), "gpt-5.1-codex")

    def test_allowed_efforts_follow_registry(self) -> None:
        self.assertEqual(allowed_efforts_for_model("gpt-5.4"), frozenset(("none", "low", "medium", "high", "xhigh")))
        self.assertEqual(allowed_efforts_for_model("gpt-5.4-mini"), frozenset(("low", "medium", "high", "xhigh")))
        self.assertEqual(allowed_efforts_for_model("gpt-5.1-codex"), frozenset(("low", "medium", "high")))

    def test_public_models_include_variants(self) -> None:
        model_ids = list_public_models(expose_reasoning_models=True)
        self.assertIn("gpt-5.4", model_ids)
        self.assertIn("gpt-5.4-mini", model_ids)
        self.assertIn("gpt-5.3-codex-spark", model_ids)
        self.assertIn("gpt-5.4-none", model_ids)
        self.assertIn("gpt-5.4-mini-xhigh", model_ids)
        self.assertNotIn("gpt-5.4-mini-none", model_ids)
        self.assertIn("gpt-5.1-codex-max-xhigh", model_ids)
        self.assertNotIn("codex-mini-high", model_ids)


if __name__ == "__main__":
    unittest.main()
