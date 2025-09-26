# Contributing to ChatMock

We welcome thoughtful improvements. This guide calls out the expectations that keep reviews quick and the project stable.

## Mindset
- Open an issue before large or risky efforts so scope is agreed up front.
- Keep pull requests focused and easy to follow; break sweeping changes into a series when possible.
- Treat documentation, code, and packaging (CLI, Docker, GUI) as a single surface—updates should stay in sync.

## Getting Set Up
- Review the Quickstart section in README.md and choose the path (CLI, Docker, GUI) that matches your work.
- Confirm you can log in and serve a local instance, then make a couple of sample requests to understand current behaviour.
- Note any manual verification you perform; you will reference it later in the PR body.

## Working With Core Files
- `prompt.md` and related Codex harness files are sensitive. Do not modify them or move entry points without prior maintainer approval.
- Be cautious with parameter names, response payload shapes, and file locations consumed by downstream clients. Coordinate before changing them.
- When touching shared logic, update both OpenAI and Ollama routes, plus any CLI/GUI code that depends on the same behaviour.

## Designing Features and Fixes
- Prefer opt-in flags or config switches for new capabilities; leave defaults unchanged until maintainers confirm the rollout plan.
- Document any safety limits, fallback paths, or external dependencies introduced by your change.
- Validate compatibility with popular clients (e.g. Jan, Raycast, custom OpenAI SDKs) when responses or streaming formats shift.

## Pull Request Checklist
- [ ] Rebased on the latest `main` and issue reference included when applicable.
- [ ] Manual verification steps captured under "How to try locally" in the PR body.
- [ ] README.md, DOCKER.md, and other docs updated—or explicitly noted as not required.
- [ ] No generated artefacts or caches staged (`build/`, `dist/`, `__pycache__/`, `.pytest_cache/`, etc.).
- [ ] Critical paths (`prompt.md`, routing modules, public parameter names) reviewed for unintended edits and discussed with maintainers if changes were necessary.

## Review Etiquette
- Address inline feedback point-by-point and resolve threads only after the fix lands.
- If you need guidance, leave a concise comment instead of force pushing speculative changes.
- Before asking for re-review, ensure your PR title, body, and checklist reflect the latest state.

## Need Help?
- Unsure about scope, flags, or downstream impact? Start the conversation in an issue or discussion.
- If a section of this guide feels ambiguous, suggest wording in your PR so future contributors benefit too.
