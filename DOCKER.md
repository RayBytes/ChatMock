# Docker Deployment

## Quick Start
1) Setup env:
   cp .env.example .env

2) Build the image:
   docker compose build

3) Login:
   docker compose run --rm --service-ports chatmock-login login
   - The command prints an auth URL, copy paste it into your browser.
   - If your browser cannot reach the container's localhost callback, copy the full redirect URL from the browser address bar and paste it back into the terminal when prompted.
   - Server should stop automatically once it receives the tokens and they are saved.

4) Start the server:
   docker compose up -d chatmock

5) Free to use it in whichever chat app you like!

## Configuration
Set options in `.env` or pass environment variables:
- `PORT`: Container listening port (default 8000)
- `PUID`: User ID to run the container as (default 1000)
- `PGID`: Group ID to run the container as (default 1000)
- `VERBOSE`: `true|false` to enable request/stream logs
- `CHATGPT_LOCAL_REASONING_EFFORT`: minimal|low|medium|high
- `CHATGPT_LOCAL_REASONING_SUMMARY`: auto|concise|detailed|none
- `CHATGPT_LOCAL_REASONING_COMPAT`: legacy|o3|think-tags|current
- `CHATGPT_LOCAL_DEBUG_MODEL`: force model override (e.g., `gpt-5`)
- `CHATGPT_LOCAL_CLIENT_ID`: OAuth client id override (rarely needed)
- `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS`: `true|false` to add reasoning model variants to `/v1/models`
- `CHATGPT_LOCAL_ENABLE_WEB_SEARCH`: `true|false` to enable default web search tool

### User/Group IDs (PUID/PGID)
To avoid permission issues with mounted volumes, you can set `PUID` and `PGID` to match your host user:
```bash
# Find your user's UID and GID
id -u  # Returns your user ID
id -g  # Returns your group ID

# Set in .env file
PUID=1000
PGID=1000
```

The container will run as the specified user, ensuring that files created in mounted volumes have the correct ownership.

## Logs
Set `VERBOSE=true` to include extra logging for debugging issues in upstream or chat app requests. Please include and use these logs when submitting bug reports.

## Test

```
curl -s http://localhost:8000/v1/chat/completions \
   -H 'Content-Type: application/json' \
   -d '{"model":"gpt-5-codex","messages":[{"role":"user","content":"Hello world!"}]}' | jq .
```
