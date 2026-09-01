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


IMAGE_ITEM = {
    "id": "ig_1",
    "type": "image_generation_call",
    "status": "completed",
    "output_format": "png",
    "size": "1024x1024",
    "result": "QUJD",
    "revised_prompt": "a blue cube",
}


def image_sse_events(usage_tokens: int = 10) -> list[dict[str, object]]:
    return [
        {"type": "response.output_item.done", "output_index": 0, "item": IMAGE_ITEM},
        {
            "type": "response.completed",
            "response": {
                "id": "resp_img",
                "status": "completed",
                "output": [],
                "tool_usage": {
                    "image_gen": {
                        "input_tokens": 1,
                        "output_tokens": usage_tokens,
                        "total_tokens": usage_tokens + 1,
                    }
                },
            },
        },
    ]


class ImageRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app(model_sync=False)
        self.client = self.app.test_client()

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_returns_b64(self, mock_start) -> None:
        mock_start.return_value = (FakeUpstream(image_sse_events()), None)
        response = self.client.post(
            "/v1/images/generations",
            json={"prompt": "a blue cube", "size": "1024x1024", "quality": "low"},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["b64_json"], "QUJD")
        self.assertEqual(body["data"][0]["revised_prompt"], "a blue cube")
        self.assertEqual(body["usage"]["output_tokens"], 10)

        sent = mock_start.call_args.args[0]
        self.assertEqual(sent["tool_choice"], {"type": "image_generation"})
        self.assertEqual(sent["tools"][0]["size"], "1024x1024")
        self.assertNotIn("n", sent["tools"][0])
        self.assertIn("1024x1024", sent["instructions"])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_repeats_request_for_n(self, mock_start) -> None:
        mock_start.side_effect = [
            (FakeUpstream(image_sse_events(4)), None),
            (FakeUpstream(image_sse_events(6)), None),
        ]
        response = self.client.post("/v1/images/generations", json={"prompt": "x", "n": 2})
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_count, 2)
        self.assertEqual(len(body["data"]), 2)
        self.assertEqual(body["usage"]["output_tokens"], 10)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_retries_without_rejected_tool_params(self, mock_start) -> None:
        rejection = json.dumps(
            {
                "error": {
                    "code": "unknown_parameter",
                    "message": "Unknown parameter: 'tools[0].quality'.",
                    "param": "tools[0].quality",
                }
            }
        ).encode("utf-8")
        mock_start.side_effect = [
            (FakeUpstream(status_code=400, content=rejection), None),
            (FakeUpstream(image_sse_events()), None),
        ]
        response = self.client.post(
            "/v1/images/generations", json={"prompt": "x", "quality": "low"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_count, 2)
        self.assertEqual(mock_start.call_args_list[1].args[0]["tools"], [{"type": "image_generation"}])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_reports_empty_result(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream([{"type": "response.completed", "response": {"id": "r", "output": []}}]),
            None,
        )
        response = self.client.post("/v1/images/generations", json={"prompt": "x"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error"]["code"], "no_image_returned")

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_reports_what_the_model_said(self, mock_start) -> None:
        """An empty result must carry the model's own words.

        The error used to assert the prompt "usually" hit moderation, which
        nobody had verified: the text that holds the real reason was collected
        by the stream reader and then dropped. Whoever hits this needs the
        reason, not a guess.
        """
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "I can't draw that logo."}],
                        },
                    },
                    {"type": "response.completed", "response": {"id": "r", "output": []}},
                ]
            ),
            None,
        )
        response = self.client.post("/v1/images/generations", json={"prompt": "x"})
        self.assertEqual(response.status_code, 502)
        body = response.get_json()["error"]
        self.assertEqual(body["code"], "no_image_returned")
        self.assertIn("draw that logo", body["message"])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_images_generations_says_when_nothing_came_back(self, mock_start) -> None:
        """No image and no text is a different failure, and says so."""
        mock_start.return_value = (
            FakeUpstream([{"type": "response.completed", "response": {"id": "r", "output": []}}]),
            None,
        )
        response = self.client.post("/v1/images/generations", json={"prompt": "x"})
        message = response.get_json()["error"]["message"]
        self.assertIn("no text either", message)

    def test_images_generations_rejects_url_response_format(self) -> None:
        response = self.client.post(
            "/v1/images/generations", json={"prompt": "x", "response_format": "url"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "unsupported_value")

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_embeds_image_as_data_url(self, mock_start) -> None:
        mock_start.return_value = (FakeUpstream(image_sse_events()), None)
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "draw a cube"}],
                "responses_tools": [{"type": "image_generation"}],
            },
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("data:image/png;base64,QUJD", body["choices"][0]["message"]["content"])

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_stream_closes_think_tag_before_image(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.reasoning_summary_text.delta", "delta": "planning"},
                    {"type": "response.output_item.done", "output_index": 0, "item": IMAGE_ITEM},
                    {"type": "response.completed", "response": {"id": "resp_img", "output": []}},
                ]
            ),
            None,
        )
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "draw a cube"}],
                "responses_tools": [{"type": "image_generation"}],
                "stream": True,
            },
        )
        content = ""
        for line in response.get_data(as_text=True).splitlines():
            if not line.startswith("data: ") or line[6:].strip() == "[DONE]":
                continue
            event = json.loads(line[6:])
            content += (event.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
        image_at = content.find("data:image/")
        self.assertGreater(image_at, -1)
        # The image is output, not reasoning: it must land after the reasoning
        # block is closed, or clients that hide <think> hide the image with it.
        self.assertIn("</think>", content[:image_at])

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_embeds_image_as_data_url(self, mock_start) -> None:
        mock_start.return_value = (FakeUpstream(image_sse_events()), None)
        response = self.client.post(
            "/api/chat",
            json={
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "draw a cube"}],
                "responses_tools": [{"type": "image_generation"}],
                "stream": False,
            },
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("data:image/png;base64,QUJD", body["message"]["content"])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_rebuilds_output_from_done_items(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.output_item.done",
                        "output_index": 1,
                        "item": {"type": "message", "role": "assistant", "content": []},
                    },
                    {"type": "response.output_item.done", "output_index": 0, "item": {"type": "reasoning"}},
                    {
                        "type": "response.completed",
                        "response": {"id": "resp_x", "status": "completed", "output": []},
                    },
                ]
            ),
            None,
        )
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.4-mini", "input": "hi", "stream": False},
        )
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["type"] for item in body["output"]], ["reasoning", "message"])


if __name__ == "__main__":
    unittest.main()
