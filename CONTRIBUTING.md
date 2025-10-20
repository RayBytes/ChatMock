# Contributing to ChatMock

We welcome thoughtful improvements. This guide calls out the expectations that keep reviews quick and the project stable.

# How should I contribute?

### Before changing code...
- Open an issue before large or risky efforts so scope is agreed up front.
- Keep pull requests focused and easy to follow & break sweeping changes into a series when possible.
- Treat documentation, code, and packaging (CLI, Docker, GUI) as a single surface (your updates should apply to all).

### Getting Set Up
- Review the Quickstart section in README.md
- Go through the codebase, and ensure you understand the current codebase. 
- Confirm you can log in and serve a local instance, then make a couple of sample requests to understand current behaviour so you know if it broke later on.

### Working With Core Files
- `prompt.md` and related Codex harness files are sensitive. Do not modify them or move entry points without prior maintainer approval.
- Be cautious with parameter names, response payload shapes, and file locations consumed by downstream clients. Coordinate before changing them.
- When touching shared logic, update both OpenAI and Ollama routes, plus any CLI/GUI code that depends on the same behaviour.

## Designing Features and Fixes
- Prefer opt-in flags or config switches for new capabilities & leave defaults unchanged until maintainers confirm the rollout plan.
- Document any limits, or external dependencies introduced by your change.
- Validate compatibility with popular clients (e.g. Jan, Raycast, custom OpenAI SDKs) when responses or streaming formats shift.

# Pull Request Checklist
- [ ] Rebased on the latest `main` and issue reference included when applicable.
- [ ] Manual verification steps captured under "How to try locally" in the PR body.
- [ ] README.md, DOCKER.md, and other docs updated—or explicitly noted as not required.
- [ ] No generated artefacts or caches staged (`build/`, `dist/`, `__pycache__/`, `.pytest_cache/`, etc.).
- [ ] Critical paths (`prompt.md`, routing modules, public parameter names) reviewed for unintended edits and discussed with maintainers if changes were necessary.

## Need Help?
- If you're not sure about about scope, flags, or how to implement a certain feature, always create an issue before hand.

Thank you for you contribution!
