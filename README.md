<div align="center">
  <h1>ChatMock
  <div align="center">
<a href="https://github.com/RayBytes/ChatMock/stargazers"><img src="https://img.shields.io/github/stars/RayBytes/ChatMock" alt="Stars Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/network/members"><img src="https://img.shields.io/github/forks/RayBytes/ChatMock" alt="Forks Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/pulls"><img src="https://img.shields.io/github/issues-pr/RayBytes/ChatMock" alt="Pull Requests Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/issues"><img src="https://img.shields.io/github/issues/RayBytes/ChatMock" alt="Issues Badge"/></a>
<a href="https://github.com/RayBytes/ChatMock/graphs/contributors"><img alt="GitHub contributors" src="https://img.shields.io/github/contributors/RayBytes/ChatMock?color=2b9348"></a>
<a href="https://github.com/RayBytes/ChatMock/blob/master/LICENSE"><img src="https://img.shields.io/github/license/RayBytes/ChatMock?color=2b9348" alt="License Badge"/></a>
</div>
  </h1>
  
  <p><b>OpenAI & Ollama compatible API powered by your ChatGPT plan.</b></p>
  <p>Use your ChatGPT Plus/Pro account to call OpenAI models from code or alternate chat UIs.</p>
  <br>
</div>

## What It Does

ChatMock runs a local server that creates an OpenAI/Ollama compatible API, and requests are then fulfilled using your authenticated ChatGPT login with the oauth client of Codex, OpenAI's coding CLI tool. This allows you to use GPT-5, GPT-5-Codex, and other models right through your OpenAI account, without requiring an api key. You are then able to use it in other chat apps or other coding tools. <br>
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

**Reminder:** When setting a baseURL in other applications, make you sure you include /v1/ at the end of the URL if you're using this as a OpenAI compatible endpoint (e.g http://127.0.0.1:8000/v1)

### Docker

Read [the docker instrunctions here](https://github.com/RayBytes/ChatMock/blob/main/DOCKER.md)

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

- Tool/Function calling 
- Vision/Image understanding
- Thinking summaries (through thinking tags)
- Thinking effort

## Notes & Limits

- Requires an active, paid ChatGPT account.
- Some context length might be taken up by internal instructions (but they dont seem to degrade the model) 
- Use responsibly and at your own risk. This project is not affiliated with OpenAI, and is a educational exercise.

# Supported models
- `gpt-5`
- `gpt-5-codex`
- `codex-mini`

# Customisation / Configuration

### Thinking effort

- `--reasoning-effort` (choice of minimal,low,medium,high)<br>
GPT-5 has a configurable amount of "effort" it can put into thinking, which may cause it to take more time for a response to return, but may overall give a smarter answer. Applying this parameter after `serve` forces the server to use this reasoning effort by default, unless overrided by the API request with a different effort set. The default reasoning effort without setting this parameter is `medium`.

### Thinking summaries

- `--reasoning-summary` (choice of auto,concise,detailed,none)<br>
Models like GPT-5 do not return raw thinking content, but instead return thinking summaries. These can also be customised by you.

### OpenAI Tools

- `--enable-web-search`<br>
You can also access OpenAI tools through this project. Currently, only web search is available.
You can enable it by starting the server with this parameter, which will allow OpenAI to determine when a request requires a web search, or you can use the following parameters during a request to the API to enable web search:
<br><br>
`responses_tools`: supports `[{"type":"web_search"}]` / `{ "type": "web_search_preview" }`<br>
`responses_tool_choice`: `"auto"` or `"none"`

#### Example usage
```json
{
  "model": "gpt-5",
  "messages": [{"role":"user","content":"Find current METAR rules"}],
  "stream": true,
  "responses_tools": [{"type": "web_search"}],
  "responses_tool_choice": "auto"
}
```

### Responses API

- `--enable-responses-api`<br>
Exposes a Responses‑compatible surface at `/v1/responses`.

**Important:** This proxies to ChatGPT's internal `backend-api/codex/responses` endpoint, which is a **restricted subset** of the official OpenAI Platform Responses API. Key differences:
- The ChatGPT endpoint **requires** `store=false` (rejects `store=true` with 400 error)
- The ChatGPT endpoint **does not support** `previous_response_id` parameter upstream
- ChatMock implements local polyfills for these features to provide a more complete API experience

What's supported
- Streaming passthrough (typed SSE events)
- Non‑stream aggregation (returns a final `response` object)
- `GET /v1/responses/{id}` when a non‑stream request is sent with `"store": true` (local storage only)
- `previous_response_id` (local threading simulation for non‑stream requests)

Start the server
```bash
python chatmock.py serve --enable-responses-api
```

Streaming example
```bash
curl -sN http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "model": "gpt-5",
    "stream": true,
    "input": [
      {"role":"user","content":[{"type":"input_text","text":"hello world"}]}
    ]
  }'
```

Non‑stream + retrieve
```bash
# Create (non‑stream) and store
CREATE=$(curl -s http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "model": "gpt-5",
    "stream": false,
    "store": true,
    "input": [{"role":"user","content":[{"type":"input_text","text":"Say hi"}]}]
  }')
ID=$(python - <<'PY'
import json,sys; print(json.loads(sys.stdin.read())['id'])
PY
<<< "$CREATE")

# Retrieve by id
curl -s http://127.0.0.1:8000/v1/responses/$ID | jq .
```

Flags & behavior
- `--responses-no-base-instructions`
  - For `/v1/responses` only: forwards client `instructions` as‑is. If the client omits or sends invalid instructions, upstream may 400. Default (flag off) injects the base prompt.
- Tokens params
  - The ChatGPT codex/responses upstream rejects `max_output_tokens` and `max_completion_tokens`. The server strips these if present.
- Storage & Threading (ChatGPT Endpoint Constraints)
  - **`store` parameter behavior:**
    - The upstream ChatGPT `backend-api/codex/responses` endpoint **requires** `store=false` (returns 400 error `"Store must be set to false"` for any other value, including when omitted)
    - This differs from the official OpenAI Platform Responses API, which supports `store=true` for server-side conversation persistence
    - ChatMock honors `store` **locally only**: when clients send `store=true`, it's used to persist aggregated non-stream responses for `GET /v1/responses/{id}` and build simple local threads
    - The server strips `store` before forwarding requests upstream (always sends `store=false` to prevent 400 errors)
  - **`previous_response_id` parameter behavior:**
    - Handled **locally only** for non-stream requests to simulate conversation threading
    - Not forwarded upstream (ChatGPT endpoint doesn't support this parameter)
    - For streaming continuity, include prior context inline in `input` rather than relying on `previous_response_id`
  - **Upstream response ID references:**
    - Referencing upstream item ids (e.g. `rs_…`) across calls is not supported by the ChatGPT endpoint
    - Include content inline, or use `previous_response_id` with `stream: false` to leverage local thread simulation
    - Inputs containing upstream response references (`rs_…`) in structural fields are sanitized server-side (those fields/items dropped, logged via `client_input_refs_sanitized`)
    - Plain text content containing `rs_…` strings is left intact

Logging & debugging
- Structured JSONL log at `responses_debug.jsonl` (enabled with `--verbose` or `CHATMOCK_RESPONSES_LOG=1`).
- Events: `request_received`, `param_stripped`, `client_input_refs_sanitized`, `input_items_sanitized`, `pre_upstream_refs_count`, `stream_start`, `upstream_error` (+ `upstream_error_body`), `nonstream_aggregated`.

### Expose reasoning models

- `--expose-reasoning-models`<br>
If your preferred app doesn’t support selecting reasoning effort, or you just want a simpler approach, this parameter exposes each reasoning level as a separate, queryable model. Each reasoning level also appears individually under ⁠/v1/models, so model pickers in your favorite chat apps will list all reasoning options as distinct models you can switch between.

## Notes
If you wish to have the fastest responses, I'd recommend setting `--reasoning-effort` to minimal, and `--reasoning-summary` to none. <br>
All parameters and choices can be seen by sending `python chatmock.py serve --h`<br>
The context size of this route is also larger than what you get access to in the regular ChatGPT app.<br>

When the model returns a thinking summary, the model will send back thinking tags to make it compatible with chat apps. **If you don't like this behavior, you can instead set `--reasoning-compat` to legacy, and reasoning will be set in the reasoning tag instead of being returned in the actual response text.**


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)




