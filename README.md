<div align="center">

# ChatMock

**Allows Codex to work in your favourite chat apps and coding tools.**

[![PyPI](https://img.shields.io/pypi/v/chatmock?color=blue&label=pypi)](https://pypi.org/project/chatmock/)
[![Python](https://img.shields.io/pypi/pyversions/chatmock)](https://pypi.org/project/chatmock/)
[![License](https://img.shields.io/github/license/RayBytes/ChatMock)](LICENSE)
[![Stars](https://img.shields.io/github/stars/RayBytes/ChatMock?style=flat)](https://github.com/RayBytes/ChatMock/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/RayBytes/ChatMock)](https://github.com/RayBytes/ChatMock/commits/main)
[![Issues](https://img.shields.io/github/issues/RayBytes/ChatMock)](https://github.com/RayBytes/ChatMock/issues)

<br>


</div>

<br>

## Install

#### Homebrew
```bash
brew tap RayBytes/chatmock
brew install chatmock
```

#### pipx / pip
```bash
pipx install chatmock
```

#### GUI
Download from [releases](https://github.com/RayBytes/ChatMock/releases) (macOS & Windows)

#### Docker
See [DOCKER.md](DOCKER.md)

<br>

## Getting Started

```bash
# 1. Sign in with your ChatGPT account
chatmock login

# 2. Start the server
chatmock serve
```

The server runs at `http://127.0.0.1:8000` by default. Use `http://127.0.0.1:8000/v1` as your base URL for OpenAI-compatible apps.

<br>

## Usage

<details open>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="anything"  # not checked
)

response = client.chat.completions.create(
    model="gpt-5.4",
    messages=[{"role": "user", "content": "hello"}]
)
print(response.choices[0].message.content)
```

</details>

<details>
<summary><b>cURL</b></summary>

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.4",
    "messages": [{"role": "user", "content": "hello"}]
  }'
```

</details>

<br>

## Supported Models

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.2`
- `gpt-5.1`
- `gpt-5`
- `gpt-5.3-codex`
- `gpt-5.3-codex-spark`
- `gpt-5.2-codex`
- `gpt-5-codex`
- `gpt-5.1-codex`
- `gpt-5.1-codex-max`
- `gpt-5.1-codex-mini`
- `codex-mini`

<br>

## Features

- Tool / function calling
- Vision / image input
- Thinking summaries (via think tags)
- Configurable thinking effort
- Fast mode for supported models
- Web search tool
- OpenAI-compatible `/v1/responses` (HTTP + WebSocket)
- Ollama-compatible endpoints
- Reasoning effort exposed as separate models (optional)

<br>

## Configuration

All flags go after `chatmock serve`. These can also be set as environment variables.

| Flag | Env var | Options | Default | Description |
|------|---------|---------|---------|-------------|
| `--reasoning-effort` | `CHATGPT_LOCAL_REASONING_EFFORT` | none, minimal, low, medium, high, xhigh | medium | How hard the model thinks |
| `--reasoning-summary` | `CHATGPT_LOCAL_REASONING_SUMMARY` | auto, concise, detailed, none | auto | Thinking summary verbosity |
| `--reasoning-compat` | `CHATGPT_LOCAL_REASONING_COMPAT` | legacy, o3, think-tags | think-tags | How reasoning is returned to the client |
| `--fast-mode` | `CHATGPT_LOCAL_FAST_MODE` | true/false | false | Priority processing for supported models |
| `--enable-web-search` | `CHATGPT_LOCAL_ENABLE_WEB_SEARCH` | true/false | false | Allow the model to search the web |
| `--expose-reasoning-models` | `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS` | true/false | false | List each reasoning level as its own model |
| `--responses-websocket-upstream` / `--no-responses-websocket-upstream` | `CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM` | true/false | false | Use websocket upstream transport for HTTP `/v1/responses` only |
| `--responses-websocket-upstream-stateful` / `--no-responses-websocket-upstream-stateful` | `CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM_STATEFUL` | true/false | false | Retain HTTP `/v1/responses` follow-up state across requests; requires websocket upstream mode |

<details>
<summary><b>Web search in a request</b></summary>

```json
{
  "model": "gpt-5.4",
  "messages": [{"role": "user", "content": "latest news on ..."}],
  "responses_tools": [{"type": "web_search"}],
  "responses_tool_choice": "auto"
}
```

</details>

<details>
<summary><b>Fast mode in a request</b></summary>

```json
{
  "model": "gpt-5.4",
  "input": "summarize this",
  "fast_mode": true
}
```

</details>

<details>
<summary><b>HTTP /v1/responses websocket upstream modes</b></summary>

- Disabled by default.
- `--responses-websocket-upstream` enables a transport-only bridge for HTTP `/v1/responses`. The client still uses HTTP, but ChatMock sends the upstream request over websocket.
- In transport-only mode, HTTP follow-up requests stay one-shot: ChatMock does not reuse an upstream websocket across requests and still does not reuse `previous_response_id` automatically.
- `--responses-websocket-upstream-stateful` adds retained follow-up state on top of websocket-upstream mode. It requires `--responses-websocket-upstream` and startup fails if websocket-upstream mode is not also enabled.
- In stateful mode, every stateful HTTP request must include a non-empty `X-Session-Id` or `session_id` header. Reuse is keyed by that explicit session id.
- In stateful mode, streaming HTTP `/v1/responses` are buffered inside ChatMock until the upstream response completes, then returned as SSE. Clients do not receive incremental SSE delivery in that mode.
- Stateful retained websocket ownership is process-local only. There is no cross-worker, cross-process, or shared-registry guarantee, so follow-up requests must reach the same ChatMock process.
- If the websocket upstream path fails, the request fails clearly instead of silently falling back to the legacy HTTP POST upstream transport.
- Rollback is a config change only: disable `--responses-websocket-upstream-stateful` and ChatMock returns to the existing one-shot websocket-bridge behavior.

Manual verification:
1. Default-off regression: start `chatmock serve --responses-websocket-upstream` without `--responses-websocket-upstream-stateful`, then send two HTTP `/v1/responses` requests with the same `X-Session-Id`. Example prompts: first `Remember the token ALPHA-42.`, then `What token did I ask you to remember?`. Confirm the second request behaves like a fresh one-shot request rather than a retained follow-up.
2. Stateful mode: restart with both `--responses-websocket-upstream` and `--responses-websocket-upstream-stateful`, then send the same two HTTP `/v1/responses` requests with the same non-empty `X-Session-Id` (or `session_id`) header. Confirm the second request continues the conversation and can answer with `ALPHA-42`.
3. For the stateful check, send the follow-up to the same ChatMock process. Multi-worker or shared-registry behavior is not provided.
4. In either websocket-upstream mode, if you intentionally break websocket upstream connectivity, confirm the request fails clearly instead of silently succeeding through the legacy HTTP POST upstream path.

</details>

<br>

## Notes

Use responsibly and at your own risk. This project is not affiliated with OpenAI.

<br>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
