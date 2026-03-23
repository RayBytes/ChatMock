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

<br>

## Notes

Use responsibly and at your own risk. This project is not affiliated with OpenAI.

<br>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
