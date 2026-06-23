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
# If you are running this on a headless server, append --headless
chatmock login

# 2. Start the server
chatmock serve
```


The server runs at `http://127.0.0.1:8000` by default. Use `http://127.0.0.1:8000/v1` as your base URL for OpenAI-compatible apps.

<br>

## Example usage

<details>
<summary><strong>Raycast Integration</strong></summary>

1. **Configure the Host URL**  
   Open your Raycast Extensions preferences, navigate to the **Ollama** settings section, and input the host URL (default is `127.0.0.1:8000`).  
   <img width="587" height="211" alt="Raycast Ollama Host URL configuration" src="https://github.com/user-attachments/assets/012c576b-189a-4b96-832d-bb054d484f2b" />

2. **Sync Your Models**  
   Click the **Sync Models** button, which will register all available models.

3. **Start Chatting**  
   Open the Raycast AI Chat interface. You will now see model slugs which you can chat with. 
</details>

<details>
<summary><strong>Terax (Agentic Terminal) Integration</strong></summary>

1. **Configure the provider settings**  
   Open your Terax settings, and switch to the **Models** tab, add a new provider (**OpenAI Compatible**), and input the host URL (default is `http://127.0.0.1:8000/v1`), along with the model IDs you wish to use (API key may be anything).  
   <img width="700" height="337" alt="image" src="https://github.com/user-attachments/assets/d1faf4e2-1969-417d-881e-5fb72f9aa252" />

2. **Favourite, and start using it!** <br>
   Go back to your main chat window, select the model by going to the OpenAI Compatible icon, and clicking the model there (you may favourite it here to quickly select it the next time if you switch between models)
   <img width="456" height="465" alt="image" src="https://github.com/user-attachments/assets/b9d2ba22-5747-4335-b095-8ec0fb2bb30c" />
</details>

<br>

## Supported Models

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.3-codex-spark`

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
| `--no-base-instructions` | `CHATGPT_LOCAL_NO_BASE_INSTRUCTIONS` | true/false | false | Do not inject ChatMock's default Codex instructions |
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

## Important notice

Use responsibly and at your own risk. This project is not affiliated with OpenAI.

<br>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
