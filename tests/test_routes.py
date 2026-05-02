from __future__ import annotations

import json
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

import chatmock.cli as cli
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


class FakeUpstreamWebsocket:
    def __init__(self, messages: list[dict[str, object]] | None = None) -> None:
        self.sent: list[str] = []
        self._messages = [json.dumps(message) for message in (messages or [])]

    def send(self, message: str) -> None:
        self.sent.append(message)

    def recv(self) -> str:
        return self._messages.pop(0)

    def close(self) -> None:
        return None


def start_test_server(app) -> tuple[str, int]:
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
    return host, port


TOOL_SEARCH_PARAMETERS = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}

TOOL_SEARCH_CHAT_TOOL = {
    "type": "function",
    "function": {
        "name": "tool_search",
        "description": "Search the workspace for relevant files and symbols.",
        "parameters": TOOL_SEARCH_PARAMETERS,
    },
}

TOOL_SEARCH_RESPONSES_TOOL = {
    "type": "function",
    "name": "tool_search",
    "description": "Search the workspace for relevant files and symbols.",
    "strict": False,
    "parameters": TOOL_SEARCH_PARAMETERS,
}


class StartupModeTests(unittest.TestCase):
    def test_create_app_defaults_client_compat(self) -> None:
        app = create_app()
        self.assertEqual(app.config["CLIENT_COMPAT"], "default")

    def test_create_app_accepts_vscode_client_compat(self) -> None:
        app = create_app(client_compat="vscode")
        self.assertEqual(app.config["CLIENT_COMPAT"], "vscode")

    @patch("chatmock.cli.cmd_serve", return_value=0)
    def test_cli_serve_defaults_client_compat(self, mock_cmd_serve) -> None:
        with patch.object(sys, "argv", ["chatmock", "serve"]):
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(mock_cmd_serve.call_args.kwargs["client_compat"], "default")

    @patch("chatmock.cli.cmd_serve", return_value=0)
    def test_cli_serve_accepts_vscode_client_compat(self, mock_cmd_serve) -> None:
        with patch.object(sys, "argv", ["chatmock", "serve", "--client-compat", "vscode"]):
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(mock_cmd_serve.call_args.kwargs["client_compat"], "vscode")

    @patch("chatmock.cli.cmd_serve", return_value=0)
    def test_cli_serve_rejects_invalid_client_compat(self, mock_cmd_serve) -> None:
        with patch.object(sys, "argv", ["chatmock", "serve", "--client-compat", "invalid"]):
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 2)
        mock_cmd_serve.assert_not_called()


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_session_state()
        self.app = create_app()
        self.client = self.app.test_client()

    def test_openai_models_list(self) -> None:
        response = self.client.get("/v1/models")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        model_ids = [item["id"] for item in body["data"]]
        self.assertIn("gpt-5.4", model_ids)
        self.assertIn("gpt-5.4-mini", model_ids)
        self.assertIn("gpt-5.3-codex-spark", model_ids)
        self.assertNotIn("claude-sonnet-4-5", model_ids)

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
    def test_chat_completions_preserves_upstream_json_error_object(self, mock_start) -> None:
        upstream_error = {
            "error": {
                "message": "Unknown tool: tool_search",
                "type": "invalid_request_error",
                "param": "tools[0].name",
                "code": "unknown_tool",
            }
        }
        mock_start.return_value = (
            FakeUpstream(
                status_code=400,
                content=json.dumps(upstream_error).encode("utf-8"),
                text=json.dumps(upstream_error),
            ),
            None,
        )

        response = self.client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.4", "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), upstream_error)

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_preserve_unknown_model_id(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {"type": "response.completed", "response": {"id": "resp-openai"}},
                ]
            ),
            None,
        )
        requested_model = "claude-sonnet-4-5"

        response = self.client.post(
            "/v1/chat/completions",
            json={"model": requested_model, "messages": [{"role": "user", "content": "hi"}]},
        )

        self.assertEqual(response.status_code, 200)
        normalized_model = mock_start.call_args.args[0]
        self.assertEqual(normalized_model, requested_model)

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_accepts_tool_search_function_tool(self, mock_start) -> None:
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
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [TOOL_SEARCH_CHAT_TOOL],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.kwargs["tools"], [TOOL_SEARCH_RESPONSES_TOOL])

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_tool_search_round_trips_through_function_call_path(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "function_call",
                            "call_id": "call_tool_search",
                            "name": "tool_search",
                            "arguments": json.dumps({"query": "workspace symbols"}),
                        },
                    },
                    {"type": "response.completed", "response": {"id": "resp-openai"}},
                ]
            ),
            None,
        )

        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [TOOL_SEARCH_CHAT_TOOL],
            },
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        tool_calls = body["choices"][0]["message"]["tool_calls"]
        self.assertEqual(tool_calls[0]["function"]["name"], "tool_search")
        self.assertEqual(
            json.loads(tool_calls[0]["function"]["arguments"]),
            {"query": "workspace symbols"},
        )

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_rejects_responses_tools_in_default_mode(self, mock_start) -> None:
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "responses_tools": [{"type": "web_search"}],
            },
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("responses_tools", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_chat_completions_rejects_responses_tool_choice_in_default_mode(self, mock_start) -> None:
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "responses_tool_choice": "none",
            },
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("responses_tool_choice", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_openai.start_upstream_request")
    def test_mixed_tools_and_responses_tools_prefer_standard_tools_contract_in_vscode_mode(self, mock_start) -> None:
        app = create_app(client_compat="vscode")
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
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [TOOL_SEARCH_CHAT_TOOL],
                "responses_tools": [{"type": "web_search"}],
                "responses_tool_choice": "none",
            },
        )

        self.assertEqual(response.status_code, 200)
        outbound_tools = mock_start.call_args.kwargs["tools"]
        self.assertEqual(outbound_tools[0], TOOL_SEARCH_RESPONSES_TOOL)
        self.assertEqual(mock_start.call_args.kwargs["tool_choice"], "none")

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

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_rejects_responses_tools_in_default_mode(self, mock_start) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "responses_tools": [{"type": "web_search"}],
            },
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("responses_tools", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_rejects_responses_tool_choice_in_default_mode(self, mock_start) -> None:
        response = self.client.post(
            "/api/chat",
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "responses_tool_choice": "none",
            },
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("responses_tool_choice", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_accepts_responses_extensions_in_vscode_mode(self, mock_start) -> None:
        app = create_app(client_compat="vscode")
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
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "responses_tools": [{"type": "web_search"}],
                "responses_tool_choice": "none",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.kwargs["tools"], [{"type": "web_search"}])
        self.assertEqual(mock_start.call_args.kwargs["tool_choice"], "none")

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_accepts_responses_tool_choice_in_vscode_mode(self, mock_start) -> None:
        app = create_app(client_compat="vscode")
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
            json={
                "model": "gpt-5.4",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "responses_tool_choice": "none",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_start.call_args.kwargs["tool_choice"], "none")

    @patch("chatmock.routes_ollama.start_upstream_request")
    def test_ollama_chat_accepts_standard_function_tools_in_both_modes(self, mock_start) -> None:
        for client_compat in ("default", "vscode"):
            with self.subTest(client_compat=client_compat):
                app = create_app(client_compat=client_compat)
                client = app.test_client()
                mock_start.reset_mock()
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
                    json={
                        "model": "gpt-5.4",
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "tools": [TOOL_SEARCH_CHAT_TOOL],
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(mock_start.call_args.kwargs["tools"], [TOOL_SEARCH_RESPONSES_TOOL])

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
    def test_responses_route_overrides_incoming_store_true(self, mock_start) -> None:
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
            json={"model": "gpt-5.4", "input": "hello", "store": True},
        )

        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertEqual(outbound_payload["store"], False)

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_rejects_chat_completions_style_tool_in_default_mode(self, mock_start) -> None:
        response = self.client.post(
            "/v1/responses",
            json={"model": "gpt-5.4", "input": "hello", "tools": [TOOL_SEARCH_CHAT_TOOL]},
        )
        body = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(body["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("chat.completions tool schema", body["error"]["message"])
        mock_start.assert_not_called()

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_accepts_chat_completions_style_tool_in_vscode_mode(self, mock_start) -> None:
        app = create_app(client_compat="vscode")
        client = app.test_client()
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

        response = client.post(
            "/v1/responses",
            json={"model": "gpt-5.4", "input": "hello", "tools": [TOOL_SEARCH_CHAT_TOOL]},
        )

        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertEqual(outbound_payload["tools"], [TOOL_SEARCH_RESPONSES_TOOL])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_accepts_standard_function_tools_in_both_modes(self, mock_start) -> None:
        for client_compat in ("default", "vscode"):
            with self.subTest(client_compat=client_compat):
                app = create_app(client_compat=client_compat)
                client = app.test_client()
                mock_start.reset_mock()
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

                response = client.post(
                    "/v1/responses",
                    json={"model": "gpt-5.4", "input": "hello", "tools": [TOOL_SEARCH_RESPONSES_TOOL]},
                )

                self.assertEqual(response.status_code, 200)
                outbound_payload = mock_start.call_args.args[0]
                self.assertEqual(outbound_payload["tools"], [TOOL_SEARCH_RESPONSES_TOOL])

    @patch("chatmock.routes_openai.start_upstream_raw_request")
    def test_responses_route_does_not_inject_web_search_when_standard_tools_present(self, mock_start) -> None:
        app = create_app(default_web_search=True)
        client = app.test_client()
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

        response = client.post(
            "/v1/responses",
            json={"model": "gpt-5.4", "input": "hello", "tools": [TOOL_SEARCH_RESPONSES_TOOL]},
        )

        self.assertEqual(response.status_code, 200)
        outbound_tools = mock_start.call_args.args[0]["tools"]
        self.assertEqual(len(outbound_tools), 1)
        self.assertFalse(any(isinstance(tool, dict) and tool.get("type") == "web_search" for tool in outbound_tools))

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
    def test_responses_route_strips_unsupported_truncation(self, mock_start) -> None:
        mock_start.return_value = (
            FakeUpstream(
                [
                    {
                        "type": "response.created",
                        "response": {"id": "resp_truncation", "object": "response", "status": "in_progress"},
                    },
                    {
                        "type": "response.completed",
                        "response": {
                            "id": "resp_truncation",
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
            json={"model": "gpt-5.4", "input": "hello", "truncation": "auto"},
        )
        self.assertEqual(response.status_code, 200)
        outbound_payload = mock_start.call_args.args[0]
        self.assertNotIn("truncation", outbound_payload)

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
    def test_responses_websocket_rejects_chat_completions_style_tool_in_default_mode(self, mock_connect, _mock_auth) -> None:
        app = create_app()
        host, port = start_test_server(app)

        with ws_connect(f"ws://{host}:{port}/v1/responses") as client:
            client.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "model": "gpt-5.4",
                        "input": "hello",
                        "tools": [TOOL_SEARCH_CHAT_TOOL],
                    }
                )
            )
            error = json.loads(client.recv())

        self.assertEqual(error["type"], "error")
        self.assertEqual(error["error"]["code"], "CLIENT_COMPAT_UNSUPPORTED")
        self.assertIn("chat.completions tool schema", error["error"]["message"])
        mock_connect.assert_not_called()

    @patch("chatmock.websocket_routes.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.websocket_routes.connect_upstream_websocket")
    def test_responses_websocket_accepts_chat_completions_style_tool_in_vscode_mode(self, mock_connect, _mock_auth) -> None:
        fake_upstream = FakeUpstreamWebsocket(
            [
                {"type": "response.created", "response": {"id": "resp_ws_1"}},
                {"type": "response.completed", "response": {"id": "resp_ws_1"}},
            ]
        )
        mock_connect.return_value = fake_upstream

        app = create_app(client_compat="vscode")
        host, port = start_test_server(app)

        with ws_connect(f"ws://{host}:{port}/v1/responses") as client:
            client.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "model": "gpt-5.4",
                        "input": "hello",
                        "tools": [TOOL_SEARCH_CHAT_TOOL],
                    }
                )
            )
            first = json.loads(client.recv())
            second = json.loads(client.recv())

        self.assertEqual(first["type"], "response.created")
        self.assertEqual(second["type"], "response.completed")
        outbound = json.loads(fake_upstream.sent[0])
        self.assertEqual(outbound["tools"], [TOOL_SEARCH_RESPONSES_TOOL])

    @patch("chatmock.websocket_routes.get_effective_chatgpt_auth", return_value=("token", "acct"))
    @patch("chatmock.websocket_routes.connect_upstream_websocket")
    def test_responses_websocket_rewrites_response_create(self, mock_connect, _mock_auth) -> None:
        fake_upstream = FakeUpstreamWebsocket(
            [
                {"type": "response.created", "response": {"id": "resp_ws_1"}},
                {
                    "type": "response.output_item.done",
                    "item": {
                        "type": "message",
                        "role": "assistant",
                        "id": "msg_1",
                        "content": [{"type": "output_text", "text": "assistant output"}],
                    },
                },
                {"type": "response.completed", "response": {"id": "resp_ws_1"}},
                {"type": "response.created", "response": {"id": "resp_ws_2"}},
                {"type": "response.completed", "response": {"id": "resp_ws_2"}},
            ]
        )
        mock_connect.return_value = fake_upstream

        app = create_app()
        host, port = start_test_server(app)

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


if __name__ == "__main__":
    unittest.main()
