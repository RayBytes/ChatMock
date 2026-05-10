# Docker Deployment

## Quick Start
1) Setup env:
   cp .env.example .env

2) Login:
   docker compose run --rm --service-ports chatmock-login login

   - The command prints an auth URL, copy paste it into your browser.
   - If your browser cannot reach the container's localhost callback, copy the full redirect URL from the browser address bar and paste it back into the terminal when prompted.
   - Server should stop automatically once it receives the tokens and they are saved.

3) Start the server:
   docker compose up -d chatmock

4) Free to use it in whichever chat app you like!

## Configuration
Set options in `.env` or pass environment variables:
- `PORT`: Container listening port (default 8000)
- `CHATMOCK_IMAGE`: image tag to run (default `storagetime/chatmock:latest`)
- `VERBOSE`: `true|false` to enable request/stream logs
- `CHATGPT_LOCAL_REASONING_EFFORT`: minimal|low|medium|high|xhigh
- `CHATGPT_LOCAL_REASONING_SUMMARY`: auto|concise|detailed|none
- `CHATGPT_LOCAL_REASONING_COMPAT`: legacy|o3|think-tags|current
- `CHATGPT_LOCAL_FAST_MODE`: `true|false` to enable fast mode by default for supported models
- `CHATGPT_LOCAL_CLIENT_ID`: OAuth client id override (rarely needed)
- `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS`: `true|false` to add reasoning model variants to `/v1/models`
- `CHATGPT_LOCAL_ENABLE_WEB_SEARCH`: `true|false` to enable default web search tool
- `CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM`: `true|false` to opt into websocket upstream transport for HTTP `/v1/responses` (default `false`)

## `/v1/responses` websocket upstream
Set `CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM=true` to opt into websocket upstream transport for HTTP `/v1/responses` only.

- The client-facing request still uses HTTP.
- HTTP follow-up requests still do not use `previous_response_id` in this mode.
- ChatMock does not reuse an upstream websocket across separate HTTP requests.
- If the websocket upstream path fails, the request fails clearly instead of silently falling back to the legacy HTTP POST upstream transport.

## Logs
Set `VERBOSE=true` to include extra logging for troubleshooting upstream or chat app requests. Please include and use these logs when submitting bug reports.

## Manual verification
Disabled mode (`CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM=false` or unset):

```bash
curl -s http://localhost:8000/v1/responses \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5.4","input":"Hello world!"}' | jq .
```

Confirm the default HTTP `/v1/responses` path works with the mode disabled.

Enabled mode (`CHATGPT_LOCAL_RESPONSES_WEBSOCKET_UPSTREAM=true`):

1. Restart `chatmock` after changing the environment variable, then rerun the same HTTP `/v1/responses` request.
2. Confirm the request still works with the websocket bridge enabled.
3. Send an HTTP follow-up `/v1/responses` request and confirm `previous_response_id` behaviour is unchanged.
4. If you intentionally break websocket upstream connectivity, confirm the request fails clearly instead of silently succeeding through the legacy HTTP POST upstream path.

## Test

```
curl -s http://localhost:8000/v1/chat/completions \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5-codex","messages":[{"role":"user","content":"Hello world!"}]}' | jq .
```
