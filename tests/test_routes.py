from __future__ import annotations

import inspect
import json
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from chatmock import responses_websocket_bridge
from chatmock.app import create_app
from chatmock.responses_api import normalize_responses_payload
from chatmock.session import reset_session_state
from flask import Response
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


def make_json_response(body: dict[str, object], *, status_code: int = 200) -> Response:
    return Response(json.dumps(body), status=status_code, mimetype="application/json")


def make_sse_response(payload: bytes, *, status_code: int = 200) -> Response:
    return Response(payload, status=status_code, mimetype="text/event-stream")


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_normalize_responses_payload_defaults_store_false_when_omitted(self) -> None:
        normalized = normalize_responses_payload(
            {"model": "gpt-5.4", "input": "hello"},
            config=self.app.config,
        )

        self.assertEqual(normalized.payload["store"], False)

    def test_normalize_responses_payload_forces_store_false_when_explicit_true(self) -> None:
        normalized = normalize_responses_payload(
            {"model": "gpt-5.4", "input": "hello", "store": True},
            config=self.app.config,
        )

        self.assertEqual(normalized.payload["store"], False)

    def test_create_app_defaults_responses_websocket_upstream_disabled(self) -> None:
        self.assertFalse(self.app.config["RESPONSES_WEBSOCKET_UPSTREAM"])

    def test_create_app_can_enable_responses_websocket_upstream(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        self.assertTrue(app.config["RESPONSES_WEBSOCKET_UPSTREAM"])

    def test_openai_models_list(self) -> None:
        response = self.client.get("/v1/models")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        model_ids = [item["id"] for item in body["data"]]
        self.assertIn("gpt-5.4", model_ids)
        self.assertIn("gpt-5.4-mini", model_ids)
        self.assertIn("gpt-5.3-codex-spark", model_ids)

    def test_ollama_tags_list(self) -> None:
        response = self.client.get("/api/tags")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        model_names = [item["name"] for item in body["models"]]
        self.assertIn("gpt-5.4", model_names)
        self.assertIn("gpt-5.4-mini", model_names)

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
        app = create_app(debug_model="gpt-5.4")
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
        app = create_app(debug_model="gpt-5.4")
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
        app = create_app(fast_mode=True)
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
    def test_responses_route_forces_explicit_store_true_to_false(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.created",
                        "response": {"id": "resp_store", "object": "response", "status": "in_progress"},
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_store",
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
            json={"model": "gpt5.4-mini", "input": "hello", "store": True},
        )

        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertEqual(outbound_payload["store"], False)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_honors_debug_model_override(self, mock_start) -> None:
        app = create_app(debug_model="gpt-5.4")
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
                "previous_response_id": "resp_client_supplied",
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

        app = create_app()

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


class ResponsesWebsocketUpstreamContractTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_disabled_mode_keeps_http_upstream_transport(self) -> None:
        with (
            patch("chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket") as mock_bridge,
            patch("chatmock.routes_openai.start_upstream_raw_request") as mock_start,
        ):
            mock_start.return_value = (
                FakeUpstream(
                    [
                        {
                            "type": "response.created",
                            "response": {"id": "resp_http_1", "object": "response", "status": "in_progress"},
                        },
                        {
                            "type": "response.completed",
                            "response": {
                                "id": "resp_http_1",
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
                json={"model": "gpt-5.4", "input": "hello"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["id"], "resp_http_1")
        mock_start.assert_called_once()
        mock_bridge.assert_not_called()

    def test_enabled_mode_uses_websocket_bridge_for_non_stream_requests(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()

        with (
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_json_response(
                {
                    "id": "resp_ws_nonstream",
                    "object": "response",
                    "status": "completed",
                    "output": [],
                }
            )

            response = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["id"], "resp_ws_nonstream")
        mock_bridge.assert_called_once()
        self.assertFalse(mock_bridge.call_args.kwargs["stream"])
        self.assertTrue(mock_bridge.call_args.kwargs["payload"]["stream"])
        self.assertNotIn("previous_response_id", mock_bridge.call_args.kwargs["payload"])

    def test_enabled_mode_keeps_route_level_previous_response_id_policy_disabled(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()
        prepared_payload = {
            "model": "gpt-5.4",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                }
            ],
            "instructions": "base instructions",
            "reasoning": {"effort": "medium", "summary": "auto"},
            "include": ["reasoning.encrypted_content"],
            "store": False,
            "prompt_cache_key": "session-fixed",
        }

        with (
            patch(
                "chatmock.routes_openai.prepare_responses_request_for_session",
                return_value=SimpleNamespace(payload=prepared_payload, session_id="session-fixed"),
            ) as mock_prepare,
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_json_response(
                {
                    "id": "resp_ws_nonstream",
                    "object": "response",
                    "status": "completed",
                    "output": [],
                }
            )

            response = client.post(
                "/v1/responses",
                json={
                    "model": "gpt-5.4",
                    "previous_response_id": "resp_client_supplied",
                    "input": "hello",
                },
                headers={"X-Session-Id": "session-fixed"},
            )

        self.assertEqual(response.status_code, 200)
        mock_prepare.assert_called_once()
        self.assertEqual(mock_prepare.call_args.args[0], "session-fixed")
        self.assertFalse(mock_prepare.call_args.kwargs["allow_previous_response_id"])
        self.assertNotIn("previous_response_id", mock_bridge.call_args.kwargs["payload"])

    def test_enabled_mode_uses_websocket_bridge_for_streaming_requests(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()

        with (
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_sse_response(
                b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n'
            )

            response = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello", "stream": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/event-stream"))
        self.assertIn("response.output_text.delta", response.get_data(as_text=True))
        mock_bridge.assert_called_once()
        self.assertTrue(mock_bridge.call_args.kwargs["stream"])
        self.assertTrue(mock_bridge.call_args.kwargs["payload"]["stream"])

    def test_enabled_mode_keeps_http_previous_response_id_disabled(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()
        class FakeUpstreamWebsocket:
            def __init__(self, messages: list[str]) -> None:
                self.sent: list[str] = []
                self._messages = list(messages)

            def send(self, message: str) -> None:
                self.sent.append(message)

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                return None

        first_upstream = FakeUpstreamWebsocket(
            [
                json.dumps({"type": "response.created", "response": {"id": "resp_ws_1", "object": "response", "status": "in_progress"}}),
                json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_ws_1",
                            "object": "response",
                            "status": "completed",
                            "output": [
                                {
                                    "type": "message",
                                    "role": "assistant",
                                    "id": "msg_1",
                                    "content": [{"type": "output_text", "text": "assistant output"}],
                                }
                            ],
                        },
                    }
                ),
            ]
        )
        second_upstream = FakeUpstreamWebsocket(
            [
                json.dumps({"type": "response.created", "response": {"id": "resp_ws_2", "object": "response", "status": "in_progress"}}),
                json.dumps(
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_ws_2",
                            "object": "response",
                            "status": "completed",
                            "output": [],
                        },
                    }
                ),
            ]
        )

        with (
            patch("chatmock.responses_websocket_bridge.get_effective_chatgpt_auth", return_value=("token", "acct")),
            patch(
                "chatmock.responses_websocket_bridge.connect_upstream_websocket",
                side_effect=[first_upstream, second_upstream],
            ),
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            headers = {"X-Session-Id": "session-fixed"}
            first = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello"},
                headers=headers,
            )
            second = client.post(
                "/v1/responses",
                json={
                    "model": "gpt-5.4",
                    "input": [
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                        {
                            "type": "message",
                            "role": "assistant",
                            "id": "msg_1",
                            "content": [{"type": "output_text", "text": "assistant output"}],
                        },
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
                    ],
                },
                headers=headers,
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_payload = json.loads(first_upstream.sent[0])
        self.assertEqual(first_payload["type"], "response.create")
        self.assertEqual(first_payload["model"], "gpt-5.4")
        self.assertNotIn("previous_response_id", first_payload)
        second_payload = json.loads(second_upstream.sent[0])
        self.assertEqual(second_payload["type"], "response.create")
        self.assertEqual(second_payload["model"], "gpt-5.4")
        self.assertNotIn("previous_response_id", second_payload)
        self.assertEqual(
            second_payload["input"],
            [
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hello"}]},
                {
                    "type": "message",
                    "role": "assistant",
                    "id": "msg_1",
                    "content": [{"type": "output_text", "text": "assistant output"}],
                },
                {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "second"}]},
            ],
        )

    def test_enabled_mode_surfaces_websocket_connect_failure_as_http_error(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()

        with (
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_json_response(
                {"error": {"message": "Upstream websocket connection failed: dial tcp refused"}},
                status_code=502,
            )

            response = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(body["error"]["message"], "Upstream websocket connection failed: dial tcp refused")
        mock_bridge.assert_called_once()

    def test_enabled_mode_surfaces_midstream_connection_loss_as_http_error(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()

        with (
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_json_response(
                {"error": {"message": "Upstream websocket closed before response.completed"}},
                status_code=502,
            )

            response = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(body["error"]["message"], "Upstream websocket closed before response.completed")
        mock_bridge.assert_called_once()

    def test_enabled_mode_surfaces_malformed_upstream_events_as_http_error(self) -> None:
        app = create_app(responses_websocket_upstream=True)
        client = app.test_client()

        with (
            patch(
                "chatmock.routes_openai.responses_websocket_bridge.send_responses_request_via_websocket"
            ) as mock_bridge,
            patch(
                "chatmock.routes_openai.start_upstream_raw_request",
                side_effect=AssertionError(
                    "HTTP upstream transport should not be used when websocket upstream mode is enabled"
                ),
            ),
        ):
            mock_bridge.return_value = make_json_response(
                {"error": {"message": "Upstream websocket event payload was not a JSON object"}},
                status_code=502,
            )

            response = client.post(
                "/v1/responses",
                json={"model": "gpt-5.4", "input": "hello"},
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(body["error"]["message"], "Upstream websocket event payload was not a JSON object")
        mock_bridge.assert_called_once()


class ResponsesWebsocketBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app()

    def test_encode_sse_event_avoids_python_312_only_f_string_form(self) -> None:
        source = inspect.getsource(responses_websocket_bridge._encode_sse_event)
        self.assertNotIn('return f"data: {json.dumps(', source)
        self.assertEqual(
            responses_websocket_bridge._encode_sse_event({"type": "response.completed", "response": {"id": "resp_ws_1"}}),
            b'data: {"type":"response.completed","response":{"id":"resp_ws_1"}}\n\n',
        )

    def test_parse_upstream_websocket_event_rejects_non_object_payload(self) -> None:
        with self.assertRaisesRegex(
            responses_websocket_bridge.ResponsesWebsocketBridgeProtocolError,
            "Upstream websocket event payload was not a JSON object",
        ):
            responses_websocket_bridge.parse_upstream_websocket_event("[]")

    def test_parse_upstream_websocket_event_requires_response_object_for_completed(self) -> None:
        with self.assertRaisesRegex(
            responses_websocket_bridge.ResponsesWebsocketBridgeProtocolError,
            "Upstream websocket response.completed event is missing a response object",
        ):
            responses_websocket_bridge.parse_upstream_websocket_event('{"type":"response.completed"}')

    def test_build_upstream_request_event_keeps_existing_response_create_payload(self) -> None:
        payload = {"type": "response.create", "model": "gpt-5.4", "input": "hello", "stream": True}

        self.assertIs(
            responses_websocket_bridge._build_upstream_request_event(payload),
            payload,
        )

    @patch("chatmock.responses_websocket_bridge.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.responses_websocket_bridge.connect_upstream_websocket")
    def test_bridge_promotes_plain_http_payload_to_top_level_response_create_fields(self, mock_connect, _mock_auth) -> None:
        class FakeUpstreamWebsocket:
            def __init__(self) -> None:
                self.sent: list[str] = []
                self._messages = [
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_1", "object": "response", "status": "in_progress"}}),
                    json.dumps({"type": "response.completed", "response": {"id": "resp_ws_1", "object": "response", "status": "completed", "output": []}}),
                ]

            def send(self, message: str) -> None:
                self.sent.append(message)

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                return None

        fake_upstream = FakeUpstreamWebsocket()
        mock_connect.return_value = fake_upstream
        payload = {
            "model": "gpt-5.4",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                }
            ],
            "stream": True,
        }

        with self.app.test_request_context("/v1/responses", method="POST"):
            response = responses_websocket_bridge.send_responses_request_via_websocket(
                payload=payload,
                session_id="session-fixed",
                stream=False,
            )

        outbound = json.loads(fake_upstream.sent[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(outbound["type"], "response.create")
        self.assertEqual(outbound["model"], payload["model"])
        self.assertEqual(outbound["input"], payload["input"])
        self.assertTrue(outbound["stream"])
        self.assertNotIn("response", outbound)

    @patch("chatmock.responses_websocket_bridge.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.responses_websocket_bridge.connect_upstream_websocket")
    @patch("chatmock.responses_websocket_bridge.note_responses_final_response")
    def test_bridge_aggregates_completed_response_for_non_stream_http_clients(self, mock_note_final_response, mock_connect, _mock_auth) -> None:
        class FakeUpstreamWebsocket:
            def __init__(self) -> None:
                self.sent: list[str] = []
                self.close_calls = 0
                self._messages = [
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_1", "object": "response", "status": "in_progress"}}),
                    json.dumps({"type": "response.completed", "response": {"id": "resp_ws_1", "object": "response", "status": "completed", "output": []}}),
                ]

            def send(self, message: str) -> None:
                self.sent.append(message)

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                self.close_calls += 1
                return None

        fake_upstream = FakeUpstreamWebsocket()
        mock_connect.return_value = fake_upstream

        with self.app.test_request_context("/v1/responses", method="POST"):
            response = responses_websocket_bridge.send_responses_request_via_websocket(
                payload={"type": "response.create", "model": "gpt-5.4", "stream": True},
                session_id="session-fixed",
                stream=False,
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["id"], "resp_ws_1")
        self.assertEqual(json.loads(fake_upstream.sent[0])["model"], "gpt-5.4")
        self.assertEqual(fake_upstream.close_calls, 1)
        mock_note_final_response.assert_called_once_with("session-fixed", body)

    @patch("chatmock.responses_websocket_bridge.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.responses_websocket_bridge.connect_upstream_websocket")
    def test_bridge_translates_upstream_events_to_sse_for_streaming_http_clients(self, mock_connect, _mock_auth) -> None:
        class FakeUpstreamWebsocket:
            def __init__(self) -> None:
                self.close_calls = 0
                self._messages = [
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_1"}}),
                    json.dumps({"type": "response.output_text.delta", "delta": "hello"}),
                    json.dumps({"type": "response.completed", "response": {"id": "resp_ws_1", "output": []}}),
                ]

            def send(self, message: str) -> None:
                return None

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                self.close_calls += 1
                return None

        fake_upstream = FakeUpstreamWebsocket()
        mock_connect.return_value = fake_upstream

        with self.app.test_request_context("/v1/responses", method="POST"):
            response = responses_websocket_bridge.send_responses_request_via_websocket(
                payload={"type": "response.create", "model": "gpt-5.4", "stream": True},
                session_id="session-fixed",
                stream=True,
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/event-stream"))
        self.assertIn("response.output_text.delta", body)
        self.assertEqual(fake_upstream.close_calls, 1)
        self.assertIn('data: {"type":"response.completed","response":{"id":"resp_ws_1","output":[]}}', body)
        self.assertNotIn("data: [DONE]", body)

    @patch("chatmock.responses_websocket_bridge.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.responses_websocket_bridge.connect_upstream_websocket")
    def test_bridge_stops_after_protocol_error_event_without_done_sentinel(self, mock_connect, _mock_auth) -> None:
        class FakeUpstreamWebsocket:
            def __init__(self) -> None:
                self._messages = [
                    json.dumps({"type": "response.created", "response": {"id": "resp_ws_1"}}),
                    json.dumps({"type": "response.completed"}),
                ]

            def send(self, message: str) -> None:
                return None

            def recv(self) -> str:
                return self._messages.pop(0)

            def close(self) -> None:
                return None

        mock_connect.return_value = FakeUpstreamWebsocket()

        with self.app.test_request_context("/v1/responses", method="POST"):
            response = responses_websocket_bridge.send_responses_request_via_websocket(
                payload={"type": "response.create", "model": "gpt-5.4", "stream": True},
                session_id="session-fixed",
                stream=True,
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith("text/event-stream"))
        self.assertIn('data: {"type":"response.created","response":{"id":"resp_ws_1"}}', body)
        self.assertIn('data: {"type":"error","status_code":502,"error":{"message":"Upstream websocket response.completed event is missing a response object"}}', body)
        self.assertNotIn("data: [DONE]", body)


if __name__ == "__main__":
    unittest.main()
