from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from chatmock.app import create_app
from chatmock.codex_status import reset_account_info_cache
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
    def test_responses_route_reconstructs_non_stream_output_from_item_events(self, mock_start) -> None:
        output = [
            {
                "type": "reasoning",
                "id": "reasoning_1",
                "summary": [{"type": "summary_text", "text": "Need the tool."}],
                "encrypted_content": "encrypted",
            },
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "get_time",
                "arguments": '{"city":"Paris"}',
                "status": "completed",
            },
            {
                "type": "message",
                "role": "assistant",
                "id": "msg_1",
                "status": "completed",
                "content": [{"type": "output_text", "text": '{"city":"Paris"}'}],
            },
        ]
        events = [
            {
                "type": "response.created",
                "response": {"id": "resp_items", "object": "response", "status": "in_progress"},
            },
            *[
                {"type": "response.output_item.done", "output_index": index, "item": output[index]}
                # Completion order is not output order; the protocol supplies
                # output_index so non-stream aggregation can reconstruct it.
                for index in (2, 0, 1)
            ],
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_items",
                    "object": "response",
                    "status": "completed",
                    "output": [],
                },
            },
        ]
        mock_start.return_value = (
            FakeUpstream(events, headers={"Content-Type": "text/event-stream"}),
            None,
        )

        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.6-luna", "input": "Return structured output."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["output"], output)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_keeps_output_from_completed_response(self, mock_start) -> None:
        authoritative = {
            "type": "message",
            "role": "assistant",
            "id": "msg_final",
            "content": [{"type": "output_text", "text": "final"}],
        }
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "message",
                            "role": "assistant",
                            "id": "msg_event",
                            "content": [{"type": "output_text", "text": "event"}],
                        },
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_final",
                            "object": "response",
                            "status": "completed",
                            "output": [authoritative],
                        },
                    },
                ],
                headers={"Content-Type": "text/event-stream"},
            ),
            None,
        )

        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.6-luna", "input": "hello"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["output"], [authoritative])

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


def _unsigned_jwt(claims: dict[str, object]) -> str:
    import base64

    def _b64(obj: dict[str, object]) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(claims)}.sig"


ACCESS_TOKEN = "access-token-secret-do-not-leak"
ID_TOKEN_CLAIMS = {
    "email": "athlete@example.com",
    "name": "Athlete Example",
    "preferred_username": "athlete",
    "https://api.openai.com/auth": {"chatgpt_account_id": "acct_0123456789"},
}
ACCESS_TOKEN_CLAIMS = {"https://api.openai.com/auth": {"chatgpt_plan_type": "pro"}}

USAGE_HEADERS = {
    "x-codex-primary-used-percent": "12.5",
    "x-codex-primary-window-minutes": "10080",
    "x-codex-primary-reset-after-seconds": "345600",
    "x-codex-secondary-used-percent": "3",
    "x-codex-secondary-window-minutes": "300",
    "x-codex-secondary-reset-after-seconds": "1799",
}

COMPLETED_EVENTS = [
    {"type": "response.created", "response": {"id": "resp_1", "object": "response", "status": "in_progress"}},
    {
        "type": "response.output_item.done",
        "output_index": 0,
        "item": {"id": "msg_1", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "ok"}]},
    },
    {"type": "response.completed", "response": {"id": "resp_1", "object": "response", "status": "completed", "output": []}},
]


class CodexStatusTests(unittest.TestCase):
    """GET /v1/status reports the signed-in account and the last usage snapshot."""

    def setUp(self) -> None:
        reset_session_state()
        reset_account_info_cache()
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        env = patch.dict(os.environ, {"CHATGPT_LOCAL_HOME": home.name})
        env.start()
        self.addCleanup(env.stop)
        self.app = create_app(model_sync=False, verbose=True)
        self.client = self.app.test_client()

    def _signed_in(self):
        id_token = _unsigned_jwt(ID_TOKEN_CLAIMS)
        access_token = ACCESS_TOKEN + "." + _unsigned_jwt(ACCESS_TOKEN_CLAIMS).split(".", 1)[1]
        return patch(
            "chatmock.codex_status.load_chatgpt_tokens",
            return_value=(access_token, "acct_0123456789", id_token),
        )

    @patch("chatmock.codex_status.load_chatgpt_tokens", return_value=(None, None, None))
    def test_status_before_any_request_reports_nothing(self, _tokens) -> None:
        response = self.client.get("/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"account": None, "rate_limits": None})
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_call_feeds_the_status_snapshot(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(COMPLETED_EVENTS, headers={"Content-Type": "text/event-stream", **USAGE_HEADERS}),
            None,
        )
        with self._signed_in():
            response = self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"})
            self.assertEqual(response.status_code, 200)
            # Nothing rides on the reply itself; the data is served by /v1/status.
            for name in USAGE_HEADERS:
                self.assertNotIn(name, response.headers)
            status = self.client.get("/v1/status").get_json()
        self.assertEqual(
            status["account"],
            {
                "name": "Athlete Example",
                "email": "athlete@example.com",
                "plan_type": "pro",
                "account_id": "acct_0123456789",
            },
        )
        self.assertEqual(
            status["rate_limits"]["primary"],
            {"used_percent": 12.5, "window_minutes": 10080, "resets_in_seconds": 345600},
        )
        self.assertEqual(
            status["rate_limits"]["secondary"],
            {"used_percent": 3.0, "window_minutes": 300, "resets_in_seconds": 1799},
        )
        self.assertTrue(status["rate_limits"]["captured_at"])

    @patch("chatmock.codex_status.load_chatgpt_tokens", return_value=(None, None, None))
    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_partial_usage_is_stored_without_invention(self, mock_start, _tokens) -> None:
        partial = {
            "x-codex-primary-used-percent": "0",
            "x-codex-primary-window-minutes": "10080",
            "x-codex-primary-reset-after-seconds": "600",
        }
        mock_start.return_value = (
            FakeUpstream(COMPLETED_EVENTS, headers={"Content-Type": "text/event-stream", **partial}),
            None,
        )
        self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"})
        status = self.client.get("/v1/status").get_json()
        self.assertEqual(
            status["rate_limits"]["primary"],
            {"used_percent": 0.0, "window_minutes": 10080, "resets_in_seconds": 600},
        )
        self.assertIsNone(status["rate_limits"]["secondary"])

    @patch("chatmock.codex_status.load_chatgpt_tokens", return_value=(None, None, None))
    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_usage_is_recorded_even_on_upstream_errors(self, mock_start, _tokens) -> None:
        mock_start.return_value = (
            FakeUpstream(
                status_code=429,
                headers={"Content-Type": "application/json", **USAGE_HEADERS},
                content=json.dumps({"error": {"message": "usage limit reached"}}).encode("utf-8"),
                text="usage limit reached",
            ),
            None,
        )
        response = self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"})
        self.assertEqual(response.status_code, 429)
        status = self.client.get("/v1/status").get_json()
        self.assertEqual(status["rate_limits"]["primary"]["used_percent"], 12.5)

    def test_account_falls_back_through_email_and_username(self) -> None:
        no_name = {k: v for k, v in ID_TOKEN_CLAIMS.items() if k != "name"}
        with patch(
            "chatmock.codex_status.load_chatgpt_tokens",
            return_value=("a.b.c", "acct_0123456789", _unsigned_jwt(no_name)),
        ):
            account = self.client.get("/v1/status").get_json()["account"]
        self.assertEqual(account["name"], "athlete@example.com")
        # No plan claim on that access token: the plan stays unknown rather than defaulting.
        self.assertNotIn("plan_type", account)

        reset_account_info_cache()
        username_only = {"preferred_username": "athlete"}
        with patch(
            "chatmock.codex_status.load_chatgpt_tokens",
            return_value=(None, None, _unsigned_jwt(username_only)),
        ):
            account = self.client.get("/v1/status").get_json()["account"]
        self.assertEqual(account, {"name": "athlete"})

    def test_account_info_is_derived_once_not_per_request(self) -> None:
        with self._signed_in() as loader:
            first = self.client.get("/v1/status").get_json()
            second = self.client.get("/v1/status").get_json()
        self.assertEqual(first["account"]["name"], "Athlete Example")
        self.assertEqual(second, first)
        # The auth file was parsed for the first request only; while it is
        # unchanged on disk, later requests reuse the derived info.
        self.assertEqual(loader.call_count, 1)

    @patch("chatmock.codex_status.load_chatgpt_tokens", return_value=(None, None, None))
    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_upstream_request_keeps_model_effort_stream_and_store(self, mock_start, _tokens) -> None:
        mock_start.return_value = (
            FakeUpstream(
                headers={"Content-Type": "text/event-stream"},
                content=b'data: {"type":"response.completed","response":{"id":"resp_1","status":"completed","output":[]}}\n\n',
            ),
            None,
        )
        # The static catalog lists no `none` for gpt-5.6-luna; upstream accepts it (issue #116).
        response = self.client.post(
            "/v1/responses",
            json={
                "model": "gpt-5.6-luna",
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
                "tools": [],
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "store": False,
                "stream": True,
                "reasoning": {"effort": "none"},
            },
        )
        self.assertEqual(response.status_code, 200)
        sent = mock_start.call_args.args[0]
        self.assertEqual(sent["model"], "gpt-5.6-luna")
        self.assertEqual(sent["reasoning"]["effort"], "none")
        self.assertIs(sent["stream"], True)
        self.assertIs(sent["store"], False)
        self.assertEqual(sent["tools"], [])
        self.assertEqual(sent["tool_choice"], "auto")
        self.assertIs(sent["parallel_tool_calls"], False)
        self.assertEqual(
            sent["input"],
            [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        )

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_no_token_reaches_the_status_body_headers_or_logs(self, mock_start) -> None:
        import contextlib
        import io

        mock_start.return_value = (
            FakeUpstream(COMPLETED_EVENTS, headers={"Content-Type": "text/event-stream", **USAGE_HEADERS}),
            None,
        )
        captured = io.StringIO()
        with self._signed_in(), contextlib.redirect_stdout(captured):
            self.client.post("/v1/responses", json={"model": "gpt-5.4", "input": "hello"})
            response = self.client.get("/v1/status")
        self.assertEqual(response.status_code, 200)
        id_token = _unsigned_jwt(ID_TOKEN_CLAIMS)
        secrets = (ACCESS_TOKEN, id_token, id_token.split(".")[1], "Bearer ")
        body = response.get_data(as_text=True)
        header_blob = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
        logs = captured.getvalue()
        for secret in secrets:
            self.assertNotIn(secret, body)
            self.assertNotIn(secret, header_blob)
            self.assertNotIn(secret, logs)


if __name__ == "__main__":
    unittest.main()
