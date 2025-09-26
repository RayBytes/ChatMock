# Repository Guidelines

## Project Structure & Key Files
- `chatmock/` contains the Flask proxy, OAuth/session helpers, OpenAI and Ollama routes, plus shared utilities (`utils.py`, `limits.py`, `config.py`).
- CLI entry lives in `chatmock.py`; GUI packaging is `build.py`; Docker assets sit in `docker/`, `docker-compose.yml`, and `Dockerfile`.
- Prompt scaffolding (`prompt.md`, `prompt_gpt5_codex.md`) drives Codex agents—do not edit or relocate without prior maintainer approval.

## Build & Smoke Commands
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python chatmock.py login   # needs ChatGPT Plus/Pro credentials
python chatmock.py serve --port 8000 --verbose
```
- Docker flow: `cp .env.example .env && docker compose up --build chatmock`.
- Homebrew check: `brew tap RayBytes/chatmock && brew install chatmock` (verifies Formula/chatmock.rb).
- Basic health probe:
```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5","messages":[{"role":"user","content":"ping"}]}'
```

## Coding Style & Guardrails
- Follow PEP 8 defaults (4-space indent, snake_case funcs, CamelCase classes); keep imports grouped stdlib → third-party → local.
- Preserve public request/response fields. When behavior changes, update both `routes_openai.py` and `routes_ollama.py`, plus GUI/CLI touchpoints.
- New capabilities should ship behind explicit flags (e.g., `--enable-web-search`) and stay default-off until maintainers agree to flip them.
- Large or risky refactors (config systems, prompt edits, auth flows) require an issue first—see the maintainer feedback on PR #35.

## Verification Checklist
- Run the curl smoke test and any new CLI flags you introduce. Document the exact commands in your PR under “How to try locally.”
- For Docker or Homebrew modifications, boot that path once and note the outcome.
- GUI or packaging work: `python build.py` (ensure Pillow/toolchain present) and capture observations.
- Watch for downstream client quirks (Jan JSON parsing, Raycast behavior) when touching streaming responses; call out any trade-offs.

## Commit & Pull Request Guidelines
- Use present-tense, conventional-style commit subjects (`docs: add contributing guide`).
- Link the tracking issue in the PR description, summarize scope, and list manual verification steps.
- Keep diffs focused; avoid touching prompt files, entry points, or critical config paths without explicit sign-off.
- Resolve review threads one-by-one, reply to inline comments, and refresh docs (README.md, DOCKER.md, CONTRIBUTING.md) when behavior or flags change.
