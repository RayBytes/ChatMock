from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from chatmock.app import create_app


class FakeUpstream:
    def __init__(self, events: list[dict[str, object]], status_code: int = 200) -> None:
        self._events = events
        self.status_code = status_code
        self.headers = {}
        self.content = b""
        self.text = ""

    def iter_lines(self, decode_unicode: bool = False):
        for event in self._events:
            payload = f"data: {json.dumps(event)}"
            yield payload if decode_unicode else payload.encode("utf-8")

    def close(self) -> None:
        return None


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.client = self.app.test_client()

    def test_openai_models_list(self) -> None:
        response = self.client.get("/v1/models")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("gpt-5.4", [item["id"] for item in body["data"]])

    def test_ollama_tags_list(self) -> None:
        response = self.client.get("/api/tags")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("gpt-5.4", [item["name"] for item in body["models"]])

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed", "response": {"id": "resp-openai"}},
                ]
            ),
            None,
        )
        response = self.client.post(
            "/v1/chat/completions",
            json={"model": "gpt5.4", "messages": [{"role": "user", "content": "hi"}]},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "hello")
        self.assertEqual(body["model"], "gpt5.4")

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed"},
                ]
            ),
            None,
        )
        response = self.client.post(
            "/api/chat",
            json={"model": "gpt-5.4", "messages": [{"role": "user", "content": "hi"}], "stream": False},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["message"]["content"], "hello")
        self.assertEqual(body["model"], "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
