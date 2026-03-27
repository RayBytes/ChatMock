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

   - Compose publishes the same host port as `PORT` from `.env`, so changing `PORT` changes the URL you should use.

4) Free to use it in whichever chat app you like!

## Configuration
Set options in `.env` or pass environment variables:
- `PORT`: Container listening port and published host port for the `chatmock` service (default 8000)
- `CHATMOCK_IMAGE`: image tag to run (default `storagetime/chatmock:latest`)
- `VERBOSE`: `true|false` to enable request/stream logs
- `CHATGPT_LOCAL_REASONING_EFFORT`: minimal|low|medium|high|xhigh
- `CHATGPT_LOCAL_REASONING_SUMMARY`: auto|concise|detailed|none
- `CHATGPT_LOCAL_REASONING_COMPAT`: legacy|o3|think-tags|current
- `CHATGPT_LOCAL_FAST_MODE`: `true|false` to enable fast mode by default for supported models
- `CHATGPT_LOCAL_CLIENT_ID`: OAuth client id override (rarely needed)
- `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS`: `true|false` to add reasoning model variants to `/v1/models`
- `CHATGPT_LOCAL_ENABLE_WEB_SEARCH`: `true|false` to enable default web search tool

## Logs
Set `VERBOSE=true` to include extra logging for troubleshooting upstream or chat app requests. Please include and use these logs when submitting bug reports.

## Test

```bash
curl -s "http://localhost:${PORT:-8000}/v1/chat/completions" \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5-codex","messages":[{"role":"user","content":"Hello world!"}]}' | jq .
```
