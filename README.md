<div align="center">
  <h1>ChatMock</h1>
  <p><b>OpenAI & Ollama compatible API powered by your ChatGPT plan.</b></p>
  <p>Use your ChatGPT Plus/Pro account to call OpenAI models from code or alternate chat UIs.</p>
  <br>
</div>

## What It Does

ChatMock runs a local server that creates an OpenAI/Ollama compatible API, and requests are then fulfilled using your authenticated ChatGPT login with the oauth client of Codex, OpenAI's coding CLI tool. This allows you to use GPT-5 and other models right through your OpenAI account, without requiring an api key.
This does require a paid ChatGPT account.

## Quickstart

### Mac Users

#### GUI Application

If you're on **macOS**, you can download the GUI app from the [GitHub releases](https://github.com/RayBytes/ChatMock/releases).  
> **Note:** Since ChatMock isn't signed with an Apple Developer ID, you may need to run the following command in your terminal to open the app:
>
> ```bash
> xattr -dr com.apple.quarantine /Applications/ChatMock.app
> ```
>
> *[More info here.](https://github.com/deskflow/deskflow/wiki/Running-on-macOS)*

#### Command Line (Homebrew)

You can also install ChatMock as a command-line tool using [Homebrew](https://brew.sh/):
```
brew tap RayBytes/chatmock
brew install chatmock
```

### Python
If you wish to just simply run this as a python flask server, you are also freely welcome too.

Clone or download this repository, then cd into the project directory. Then follow the instrunctions listed below.

1. Sign in with your ChatGPT account and follow the prompts
```bash
python chatmock.py login
```
You can make sure this worked by running `python chatmock.py info`

2. After the login completes successfully, you can just simply start the local server

```bash
python chatmock.py serve
```
Then, you can simply use the address and port as the baseURL as you require (http://127.0.0.1:8000 by default)

**Reminder:** When setting a baseURL, make you sure you include /v1/ at the end of the URL if you're using this as a OpenAI compatible endpoint (e.g http://127.0.0.1:8000/v1)

## CLI Reference

Run `python chatmock.py -h` to see all commands. Running with no arguments will print help.

- `login` --- Authorize with ChatGPT and store tokens.
  - Options: `--no-browser`, `--verbose`
- `serve` --- Run local OpenAI-compatible server.
  - Options: `--config PATH`, `--host HOST`, `--port PORT`, `--verbose`,
    `--debug-model NAME`, `--reasoning-effort {minimal,low,medium,high}`,
    `--reasoning-summary {auto,concise,detailed,none}`,
    `--reasoning-compat {legacy,o3,think-tags,current}`,
    `--expose-reasoning-models`
- `info` --- Print current stored tokens and derived account id.
  - Options: `--json`
- `diagnose` --- Print resolved configuration and sanity checks.
  - Options: `--config PATH`

## Troubleshooting

- Port already in use but server still starts
  - On many systems `localhost` resolves to IPv6 first (`::1`). You can have one service on `::1:PORT` and another on `127.0.0.1:PORT` at the same time. ChatMock now warns if it detects a listener on the other stack.
  - Use `curl -4 http://localhost:8000` (IPv4) or `curl -6 http://localhost:8000` (IPv6), or target `http://127.0.0.1:8000` or `http://[::1]:8000` directly.

# Examples

### Python

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="key"  # ignored
)

resp = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "hello world"}]
)

print(resp.choices[0].message.content)
```

### curl

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role":"user","content":"hello world"}]
  }'
```

# What's supported

- Tool calling
- Vision/Image understanding
- Thinking summaries (through thinking tags)

## Notes & Limits

- Requires an active, paid ChatGPT account.
- Expect lower rate limits than what you may recieve in the ChatGPT app.
- Some context length might be taken up by internal instructions (but they dont seem to degrade the model) 
- Use responsibly and at your own risk. This project is not affiliated with OpenAI, and is a educational exercise.

# Supported models
- `gpt-5`
- `codex-mini`

# Customisation / Configuration

### Config file (YAML preferred)

You can configure the server host/port via a YAML config file. The following locations are searched in order (canonical name is `config.yaml`):

- Home locations:
  - If `~/.chatgpt-local` exists, that directory is used (legacy compatibility).
  - Otherwise, the preferred location is `~/.chatmock`.
  - You can override with `$CHATGPT_LOCAL_HOME` or `$CODEX_HOME`.

You may also specify an explicit path with `--config` or the `CHATMOCK_CONFIG` environment variable.

Example `config.yaml`:

```
server:
  host: 127.0.0.1
  port: 8000
  # verbose: false
  # expose_reasoning_models: false
  # debug_model: null

reasoning:
  effort: medium      # minimal|low|medium|high
  summary: auto       # auto|concise|detailed|none
  compat: think-tags  # legacy|o3|think-tags

oauth:
  # Optionally override Codex OAuth client id (or set env CHATGPT_LOCAL_CLIENT_ID)
  # client_id: "app_xxxxxxxxxxxxxxxxx"

login:
  # Bind host for the local OAuth helper (port is fixed at 1455)
  bind_host: 127.0.0.1

upstream:
  # Optionally override the Responses API URL
  # responses_url: https://chatgpt.com/backend-api/codex/responses

instructions:
  # Optional: path to custom instructions (prompt) file
  # path: ./my-prompt.md
```

Usage examples:

- CLI: `python chatmock.py serve --config ~/.chatmock/config.yaml`
- GUI: Defaults are pre-filled from the config; you can still override in the UI.

Precedence:
- CLI flags override config values; config overrides environment variables; environment overrides built-in defaults.

Note: On first run, a default commented `config.yaml` is created in the preferred home directory if none exists.

### Auth file (auth.json) location

ChatMock reads your auth tokens from these locations in order:

- `$CHATMOCK_HOME/auth.json`
- `$CHATGPT_LOCAL_HOME/auth.json`
- `~/.chatmock/auth.json` (preferred)
- `~/.chatgpt-local/auth.json` (legacy)
- `$CODEX_HOME/auth.json` (Codex; read-only for ChatMock)
- `~/.codex/auth.json` (Codex; read-only for ChatMock)

When you run `chatmock login`, the auth file is written only to ChatMock-controlled locations, in this order: `$CHATMOCK_HOME`, `$CHATGPT_LOCAL_HOME`, then `~/.chatmock`.
ChatMock never writes to Codex-managed locations (`$CODEX_HOME`, `~/.codex`) or `~/.chatgpt-local`.

### Thinking effort

- `--reasoning-effort` (choice of minimal,low,medium,high)<br>
GPT-5 has a configurable amount of "effort" it can put into thinking, which may cause it to take more time for a response to return, but may overall give a smarter answer. Applying this parameter after `serve` forces the server to use this reasoning effort by default, unless overrided by the API request with a different effort set. The default reasoning effort without setting this parameter is `medium`.
You can also set this via config: `reasoning.effort` in `config.yaml`.

### Thinking summaries

- `--reasoning-summary` (choice of auto,concise,detailed,none)<br>
Models like GPT-5 do not return raw thinking content, but instead return thinking summaries. These can also be customised by you.
You can also set this via config: `reasoning.summary`.

## Notes
If you wish to have the fastest responses, I'd recommend setting `--reasoning-effort` to low, and `--reasoning-summary` to none.
All parameters and choices can be seen by sending `python chatmock.py serve --h`<br>
The context size of this route is also larger than what you get access to in the regular ChatGPT app.

**When the model returns a thinking summary, the model will send back thinking tags to make it compatible with chat apps. If you don't like this behavior, you can instead set `--reasoning-compat` to legacy, and reasoning will be set in the reasoning tag instead of being returned in the actual response text.**

# TODO
- ~~Implement Ollama support~~ ✅
- Explore to see if we can make more model settings accessible
- Implement analytics (token counting, etc, to track usage)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
