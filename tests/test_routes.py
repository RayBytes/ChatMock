from __future__ import annotations

import json
import socket
import threading
import time
import unittest
from unittest.mock import patch

from chatmock.app import create_app
from chatmock.session import reset_session_state
from websockets.sync.client import connect as ws_connect


class FakeUpstream:
    def __init__(
        self,
        events: list[dict[str, object]] | None = None,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        text: str = "",
    ) -> None:
        self._events = events
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content or b""
        self.text = text

    def iter_lines(self, decode_unicode: bool = False):
        for event in self._events or []:
            payload = f"data: {json.dumps(event)}"
            yield payload if decode_unicode else payload.encode("utf-8")

    def iter_content(self, chunk_size=None):
        if self.content:
            yield self.content
            return
        for event in self._events or []:
            payload = f"data: {json.dumps(event)}\n\n".encode("utf-8")
            yield payload

    def json(self):
        return json.loads(self.content.decode("utf-8"))

    def close(self) -> None:
        return None


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app(model_sync=False)
        self.client = self.app.test_client()

    def test_openai_models_list(self) -> None:
        response = self.client.get("/v1/models")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        model_ids = [item["id"] for item in body["data"]]
        self.assertIn("gpt-5.4", model_ids)
        self.assertIn("gpt-5.4-mini", model_ids)
        self.assertIn("gpt-5.3-codex-spark", model_ids)
        self.assertIn("gpt-5.6-sol", model_ids)
        self.assertIn("gpt-5.6-terra", model_ids)
        self.assertIn("gpt-5.6-luna", model_ids)

    def test_ollama_tags_list(self) -> None:
        response = self.client.get("/api/tags")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        model_names = [item["name"] for item in body["models"]]
        self.assertIn("gpt-5.4", model_names)
        self.assertIn("gpt-5.4-mini", model_names)
        self.assertIn("gpt-5.6-sol", model_names)
        self.assertIn("gpt-5.6-terra", model_names)
        self.assertIn("gpt-5.6-luna", model_names)

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
            json={"model": "gpt5.4-mini", "messages": [{"role": "user", "content": "hi"}]},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "hello")
        self.assertEqual(body["model"], "gpt5.4-mini")

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_honors_debug_model_override(self, mock_start) -> None:
        app = create_app(debug_model="gpt-5.4", model_sync=False)
        client = app.test_client()
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed", "response": {"id": "resp-openai"}},
                ]
            ),
            None,
        )
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.3-codex", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.args[0], "gpt-5.4")

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

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_honors_debug_model_override(self, mock_start) -> None:
        app = create_app(debug_model="gpt-5.4", model_sync=False)
        client = app.test_client()
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed"},
                ]
            ),
            None,
        )
        response = client.post(
            "/api/chat",
            json={"model": "gpt-5.3-codex", "messages": [{"role": "user", "content": "hi"}], "stream": False},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.args[0], "gpt-5.4")
        self.assertEqual(body["model"], "gpt-5.4")

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_fast_mode_sets_priority_service_tier(self, mock_start) -> None:
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
            json={
                "model": "gpt-5.4",
                "fast_mode": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.kwargs["service_tier"], "priority")

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_fast_mode_false_overrides_server_default(self, mock_start) -> None:
        app = create_app(fast_mode=True, model_sync=False)
        client = app.test_client()
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed", "response": {"id": "resp-openai"}},
                ]
            ),
            None,
        )
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4",
                "fast_mode": False,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(mock_start.call_args.kwargs["service_tier"])

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_rejects_unsupported_explicit_fast_mode(self, mock_start) -> None:
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.3-codex",
                "fast_mode": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Fast mode is not supported", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_returns_completed_response_object(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.created",
                        "response": {"id": "resp_123", "object": "response", "status": "in_progress"},
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_123",
                            "object": "response",
                            "status": "completed",
                            "output": [],
                        },
                    },
                ],
                headers={"Content-Type": "text/event-stream"},
            ),
            None,
        )
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt5.4-mini", "input": "hello"},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["id"], "resp_123")
        outbound_payload = mock_start.call_args.args[0]
        self.assertEqual(outbound_payload["model"], "gpt-5.4-mini")
        self.assertEqual(outbound_payload["store"], False)
        self.assertEqual(
            outbound_payload["input"],
            [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        )
        self.assertEqual(outbound_payload["reasoning"]["effort"], "medium")
        self.assertIsInstance(outbound_payload["prompt_cache_key"], str)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_honors_debug_model_override(self, mock_start) -> None:
        app = create_app(debug_model="gpt-5.4", model_sync=False)
        client = app.test_client()
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.created",
                        "response": {"id": "resp_debug", "object": "response", "status": "in_progress"},
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_debug",
                            "object": "response",
                            "status": "completed",
                            "output": [],
                        },
                    },
                ],
                headers={"Content-Type": "text/event-stream"},
            ),
            None,
        )
        response = client.post(
            "/v1/responses",
            json={"model": "gpt-5.3-codex", "input": "hello"},
        )
        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertEqual(outbound_payload["model"], "gpt-5.4")

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_strips_unsupported_max_output_tokens(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.created",
                        "response": {"id": "resp_limit", "object": "response", "status": "in_progress"},
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_limit",
                            "object": "response",
                            "status": "completed",
                            "output": [],
                        },
                    },
                ],
                headers={"Content-Type": "text/event-stream"},
            ),
            None,
        )
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.4", "input": "hello", "max_output_tokens": 20},
        )
        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertNotIn("max_output_tokens", outbound_payload)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_does_not_use_previous_response_id_for_http_follow_up(self, mock_start) -> None:
        mock_start.side_effect = [
            (
                FakeUpstream(
                    [
                        {
                            "type": "response.created",
                            "response": {"id": "resp_1", "object": "response", "status": "in_progress"},
                        },
                        {
                            "type": "response.output_item.done",
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "id": "msg_1",
                                "content": [{"type": "output_text", "text": "assistant output"}],
                            },
                        },
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_1", "object": "response", "status": "completed", "output": []},
                        },
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
            (
                FakeUpstream(
                    [
                        {
                            "type": "response.created",
                            "response": {"id": "resp_2", "object": "response", "status": "in_progress"},
                        },
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_2", "object": "response", "status": "completed", "output": []},
                        },
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
        ]

        first = self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"})
        second = self.client.post(
            "/v1/responses",
            json={
                "model": "gpt-5.4",
                "input": [
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                    {"type": "message", "role": "assistant", "id": "msg_1", "content": [{"type": "output_text", "text": "assistant output"}]},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                ],
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        outbound_payload = mock_start.call_args_list[1].args[0]
        self.assertNotIn("previous_response_id", outbound_payload)
        self.assertEqual(
            outbound_payload["input"],
            [
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                {"type": "message", "role": "assistant", "id": "msg_1", "content": [{"type": "output_text", "text": "assistant output"}]},
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
            ],
        )

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_falls_back_to_full_create_when_non_input_fields_change(self, mock_start) -> None:
        mock_start.side_effect = [
            (
                FakeUpstream(
                    [
                        {
                            "type": "response.created",
                            "response": {"id": "resp_1", "object": "response", "status": "in_progress"},
                        },
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_1", "object": "response", "status": "completed", "output": []},
                        },
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
            (
                FakeUpstream(
                    [
                        {
                            "type": "response.created",
                            "response": {"id": "resp_2", "object": "response", "status": "in_progress"},
                        },
                        {
                            "type": "response.completed",
                            "response": {"id": "resp_2", "object": "response", "status": "completed", "output": []},
                        },
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
        ]

        headers = {"X-Session-Id": "session-fixed"}
        first = self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"}, headers=headers)
        second = self.client.post(
            "/v1/responses",
            json={
                "model": "gpt-5.4",
                "instructions": "changed",
                "input": [
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                ],
            },
            headers=headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        outbound_payload = mock_start.call_args_list[1].args[0]
        self.assertNotIn("previous_response_id", outbound_payload)
        self.assertEqual(
            outbound_payload["input"],
            [
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
            ],
        )

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_clears_reuse_state_after_error(self, mock_start) -> None:
        mock_start.side_effect = [
            (
                FakeUpstream(
                    [
                        {"type": "response.created", "response": {"id": "resp_1"}},
                        {"type": "response.completed", "response": {"id": "resp_1", "output": []}},
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
            (
                FakeUpstream(
                    [
                        {"type": "response.failed", "response": {"error": {"message": "boom"}}},
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
            (
                FakeUpstream(
                    [
                        {"type": "response.created", "response": {"id": "resp_3"}},
                        {"type": "response.completed", "response": {"id": "resp_3", "output": []}},
                    ],
                    headers={"Content-Type": "text/event-stream"},
                ),
                None,
            ),
        ]

        headers = {"X-Session-Id": "session-fixed"}
        first = self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"}, headers=headers)
        second = self.client.post(
            "/v1/responses",
            json={
                "model": "gpt-5.4",
                "input": [
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                ],
            },
            headers=headers,
        )
        third = self.client.post(
            "/v1/responses",
            json={
                "model": "gpt-5.4",
                "input": [
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "third"}]},
                ],
            },
            headers=headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 502)
        self.assertEqual(third.status_code, 200)
        outbound_payload = mock_start.call_args_list[2].args[0]
        self.assertNotIn("previous_response_id", outbound_payload)
        self.assertEqual(
            outbound_payload["input"],
            [
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "third"}]},
            ],
        )

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_stream_passthrough(self, mock_start) -> None:
        chunk = b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n'
        mock_start.return_value = (
            FakeUpstream(
                headers={"Content-Type": "text/event-stream"},
                content=chunk,
            ),
            None,
        )
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.4", "input": "hello", "stream": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("response.output_text.delta", response.get_data(as_text=True))

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_rejects_unsupported_explicit_priority(self, mock_start) -> None:
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.3-codex", "input": "hello", "service_tier": "priority"},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Fast mode is not supported", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.websocket_routes.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.websocket_routes.connect_upstream_websocket")
    def test_responses_websocket_rewrites_response_create(self, mock_connect, _mock_auth) -> None:
        class FakeUpstreamWebsocket:
            def __init__(self) -> None:
                self.sent: list[str] = []
                self._messages = [
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_1"}}),
                    json.dumps({
                        "type": "response.output_item.done",
                        "item": {
                            "type": "message",
                            "role": "assistant",
                            "id": "msg_1",
                            "content": [{"type": "output_text", "text": "assistant output"}],
                        },
                    }),
                    json.dumps({"type": "response.completed", "response": {"id": "resp_ws_1"}}),
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_2"}}),
                    json.dumps({"type": "response.completed", "response": {"id": "resp_ws_2"}}),
                ]

            def send(self, message: str) -> None:
                self.sent.append(message)

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                return None

        fake_upstream = FakeUpstreamWebsocket()
        mock_connect.return_value = fake_upstream

        app = create_app(model_sync=False)

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        sock.close()

        server_thread = threading.Thread(
            target=app.run,
            kwargs={
                "host": host,
                "port": port,
                "use_reloader": False,
                "threaded": True,
            },
            daemon=True,
        )
        server_thread.start()
        time.sleep(0.5)

        with ws_connect(f"ws://{host}:{port}/v1/responses") as client:
            client.send(json.dumps({"type": "response.create", "model": "gpt-5.4", "input": "hello", "fast_mode": True}))
            first = json.loads(client.recv())
            assistant = json.loads(client.recv())
            second = json.loads(client.recv())
            client.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "model": "gpt-5.4",
                        "fast_mode": True,
                        "input": [
                            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                            {"type": "message", "role": "assistant", "id": "msg_1", "content": [{"type": "output_text", "text": "assistant output"}]},
                            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                        ],
                    }
                )
            )
            third = json.loads(client.recv())
            fourth = json.loads(client.recv())

        self.assertEqual(first["type"], "response.created")
        self.assertEqual(assistant["type"], "response.output_item.done")
        self.assertEqual(second["type"], "response.completed")
        self.assertEqual(third["type"], "response.created")
        self.assertEqual(fourth["type"], "response.completed")
        outbound = json.loads(fake_upstream.sent[0])
        self.assertEqual(outbound["model"], "gpt-5.4")
        self.assertEqual(outbound["service_tier"], "priority")
        self.assertEqual(outbound["type"], "response.create")
        self.assertEqual(
            outbound["input"],
            [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
        )
        self.assertIn("prompt_cache_key", outbound)
        follow_up = json.loads(fake_upstream.sent[1])
        self.assertEqual(follow_up["previous_response_id"], "resp_ws_1")
        self.assertEqual(
            follow_up["input"],
            [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]}],
        )


class ResponseFormatTests(unittest.TestCase):
    SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary"],
        "properties": {"summary": {"type": "string"}},
    }

    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app(model_sync=False)
        self.client = self.app.test_client()

    def _post(self, mock_start, **extra) -> dict:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "{}"},
                    {"type": "response.completed", "response": {"id": "resp-fmt"}},
                ]
            ),
            None,
        )
        response = self.client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "hi"}], **extra},
        )
        self.assertEqual(response.status_code, 200)
        return mock_start.call_args.kwargs




    @patch("chatmock.routes_openai.start_upstream_request")
    def test_formats_that_are_not_forwarded(self, mock_start) -> None:
        self.assertIsNone(self._post(mock_start)["text_format"])
        self.assertIsNone(self._post(mock_start, response_format={"type": "text"})["text_format"])
        self.assertIsNone(
            self._post(mock_start, response_format={"type": "json_object"})["text_format"]
        )
        self.assertIsNone(
            self._post(
                mock_start, response_format={"type": "json_schema", "json_schema": {"schema": {}}}
            )["text_format"]
        )


    @patch("chatmock.routes_openai.start_upstream_request")
    def test_json_content_is_not_corrupted_by_think_tags(self, mock_start) -> None:
        events = [
            {"type": "response.reasoning_summary_text.delta", "delta": "**Weighing it up**"},
            {"type": "response.reasoning_text.delta", "delta": "the full trace"},
            {"type": "response.output_text.delta", "delta": '{"summary":"ok"}'},
            {"type": "response.completed", "response": {"id": "resp-fmt"}},
        ]

        def post(**extra):
            mock_start.return_value = (FakeUpstream(list(events)), None)
            return self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-5.6-sol",
                    "messages": [{"role": "user", "content": "hi"}],
                    **extra,
                },
            ).get_json()["choices"][0]["message"]

        self.assertTrue(post()["content"].startswith("<think>"))

        message = post(
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "r", "schema": self.SCHEMA},
            }
        )
        self.assertEqual(json.loads(message["content"]), {"summary": "ok"})
        self.assertEqual(message["reasoning_summary"], "**Weighing it up**")
        self.assertEqual(message["reasoning"], "the full trace")

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_non_think_tags_compat_is_left_alone(self, mock_start) -> None:
        client = create_app(model_sync=False, reasoning_compat="o3").test_client()
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.reasoning_summary_text.delta", "delta": "**Weighing it up**"},
                    {"type": "response.output_text.delta", "delta": '{"summary":"ok"}'},
                    {"type": "response.completed", "response": {"id": "resp-fmt"}},
                ]
            ),
            None,
        )
        message = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.6-sol",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "r", "schema": self.SCHEMA},
                },
            },
        ).get_json()["choices"][0]["message"]
        self.assertEqual(
            message["reasoning"], {"content": [{"type": "text", "text": "**Weighing it up**"}]}
        )
        self.assertEqual(json.loads(message["content"]), {"summary": "ok"})

    def _post_ollama(self, mock_start, **extra) -> dict:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.reasoning_summary_text.delta", "delta": "**Weighing it up**"},
                    {"type": "response.output_text.delta", "delta": '{"summary":"ok"}'},
                    {"type": "response.completed", "response": {"id": "resp-fmt"}},
                ]
            ),
            None,
        )
        response = self.client.post(
            "/api/chat",
            json={
                "model": "gpt-5.6-sol",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                **extra,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()


    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_bare_json_is_uncorrupted_but_not_forwarded(self, mock_start) -> None:
        body = self._post_ollama(mock_start, format="json")
        self.assertIsNone(mock_start.call_args.kwargs["text_format"])
        self.assertEqual(json.loads(body["message"]["content"]), {"summary": "ok"})



class StructuredOutputWireTests(unittest.TestCase):
    """Asserts past the start_upstream_request boundary, onto the actual payload.

    The route tests mock that call, so they pass whether or not the schema is
    ever put on the wire.
    """

    SCHEMA = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary"],
        "properties": {"summary": {"type": "string"}},
    }

    EVENTS = [
        {"type": "response.reasoning_summary_text.delta", "delta": "**T**"},
        {"type": "response.output_text.delta", "delta": '{"summary":"ok"}'},
        {"type": "response.completed", "response": {"id": "resp-wire"}},
    ]

    def setUp(self) -> None:
        reset_session_state()
        self.client = create_app(model_sync=False).test_client()

    def _send(self, mock_post, path: str, body: dict) -> tuple[dict, str]:
        mock_post.return_value = FakeUpstream(list(self.EVENTS))
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, 200)
        sent = mock_post.call_args.kwargs["json"]
        return sent, response.get_data(as_text=True)

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_schema_reaches_the_upstream_payload(self, mock_post, _auth) -> None:
        sent, _ = self._send(
            mock_post,
            "/v1/chat/completions",
            {
                "model": "gpt-5.6-sol",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "weather", "schema": self.SCHEMA},
                },
            },
        )
        self.assertEqual(
            sent["text"],
            {
                "format": {
                    "type": "json_schema",
                    "name": "weather",
                    "schema": self.SCHEMA,
                    "strict": False,
                }
            },
        )

        flat, _ = self._send(
            mock_post,
            "/v1/chat/completions",
            {
                "model": "gpt-5.6-sol",
                "messages": [{"role": "user", "content": "hi"}],
                "response_format": {
                    "type": "json_schema",
                    "name": "weather",
                    "schema": self.SCHEMA,
                    "strict": True,
                },
            },
        )
        self.assertEqual(flat["text"]["format"]["strict"], True)

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_ollama_schema_reaches_the_upstream_payload(self, mock_post, _auth) -> None:
        sent, _ = self._send(
            mock_post,
            "/api/chat",
            {
                "model": "gpt-5.6-sol",
                "stream": False,
                "messages": [{"role": "user", "content": "hi"}],
                "format": self.SCHEMA,
            },
        )
        self.assertEqual(sent["text"]["format"]["schema"], self.SCHEMA)

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_no_text_key_without_a_format(self, mock_post, _auth) -> None:
        sent, _ = self._send(
            mock_post,
            "/v1/chat/completions",
            {"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertNotIn("text", sent)

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_streaming_content_is_uncorrupted(self, mock_post, _auth) -> None:
        for path, body, extract in (
            (
                "/v1/chat/completions",
                {
                    "model": "gpt-5.6-sol",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hi"}],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": "r", "schema": self.SCHEMA},
                    },
                },
                lambda line: json.loads(line[len("data: ") :])["choices"][0]["delta"].get("content"),
            ),
            (
                "/api/chat",
                {
                    "model": "gpt-5.6-sol",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hi"}],
                    "format": self.SCHEMA,
                },
                lambda line: json.loads(line)["message"].get("content"),
            ),
        ):
            with self.subTest(path=path):
                _, raw = self._send(mock_post, path, body)
                self.assertNotIn("<think>", raw)
                chunks = []
                for line in raw.splitlines():
                    if not line.strip() or line.startswith("data: [DONE]"):
                        continue
                    try:
                        chunks.append(extract(line) or "")
                    except (ValueError, KeyError, IndexError):
                        continue
                self.assertEqual(json.loads("".join(chunks)), {"summary": "ok"})

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_schema_survives_the_rejected_tools_retry(self, mock_post, _auth) -> None:
        mock_post.side_effect = [
            FakeUpstream(status_code=400, content=b'{"error":{"message":"nope"}}'),
            FakeUpstream(list(self.EVENTS)),
        ]
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.6-sol",
                "messages": [{"role": "user", "content": "hi"}],
                "responses_tools": [{"type": "web_search"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "r", "schema": self.SCHEMA},
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)
        retried = mock_post.call_args_list[1].kwargs["json"]
        self.assertEqual(retried["text"]["format"]["schema"], self.SCHEMA)

    @patch("chatmock.upstream.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.upstream.requests.post")
    def test_streaming_keeps_think_tags_without_a_format(self, mock_post, _auth) -> None:
        _, raw = self._send(
            mock_post,
            "/v1/chat/completions",
            {
                "model": "gpt-5.6-sol",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        self.assertIn("<think>", raw)


if __name__ == "__main__":
    unittest.main()
