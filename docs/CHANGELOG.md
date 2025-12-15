# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.8] - 2025-12-15

### Added
- **Smart Input Normalization**: Properly handle different Responses API item types
  - Reasoning items: content moved to summary, preserving reasoning text
  - Function calls: content cleared as required by upstream
  - Function outputs: content converted to output field
  - Messages: content types normalized (input_text/output_text)
- **Tool Name Shortening**: Auto-shorten MCP tool names exceeding 64 char limit
  - `mcp__thinking-patterns__visual_reasoning` → `mcp__visual_reasoning`
  - Unique suffixes (~1, ~2) if needed
- **Structured Outputs**: `response_format` → `text.format` mapping
  - Supports json_schema, json_object, text types
- **Official Instructions Detection**: Skip base prompt if client sends official Codex CLI prompt
  - Saves ~2-3K context tokens
- **JSON Payload Dump**: With `VERBOSE=true`, saves full request to `responses_last_request.json`
- **Normalization Stats Logging**: `[normalize] reasoning:2 moved to summary`

### Fixed
- **Reasoning Items Error**: Fixed "array too long" error for reasoning items
  - ChatGPT upstream requires content: [] for reasoning type
- **Content Array Handling**: Proper normalization by item type, not just role

## [1.4.7] - 2025-12-14

### Added
- **API Key Authentication**: Protect your ChatMock instance with API key authentication
  - Configure via `--api-key` CLI argument or `API_KEY` / `CHATGPT_LOCAL_API_KEY` environment variable
  - Standard Bearer token authentication on all `/v1/*` endpoints
  - WebUI and health endpoints remain unprotected for convenience
- **Session Persistence**: Responses API sessions now persist across server restarts
  - Sessions saved to JSON files in `CHATGPT_LOCAL_HOME` directory
  - Automatic loading on startup
- **Improved Input Handling**: Better compatibility with Cursor IDE and Responses API clients
  - Support for `input` as list (Responses API format) in `/v1/chat/completions`
  - Support for `previous_response_id` and `conversation_id` for context continuation
  - Clear `EMPTY_INPUT` error code for debugging

### Fixed
- **ENV Variables**: `VERBOSE` and `DEBUG_LOG` environment variables now work correctly
  - Both short (`VERBOSE`, `DEBUG_LOG`) and prefixed (`CHATGPT_LOCAL_VERBOSE`, `CHATGPT_LOCAL_DEBUG`) forms supported
- **Debug Logging**: Enhanced payload debugging when `DEBUG_LOG` is enabled

## [1.4.6] - 2025-01-XX

### Added
- Support for GPT-5.1 models
- Support for GPT-5.1-Codex-Max model with xhigh reasoning effort
- Extra high (xhigh) reasoning effort option for gpt-5.1-codex-max
- Docker support with PUID and PGID environment variables for running container with different user credentials
- GitHub Actions workflow for automated Docker image builds and publishing to GitHub Container Registry
- Pre-built Docker images available at `ghcr.io/thebtf/chatmock:latest`
- `docker-compose.registry.yml` for easy deployment using pre-built images
- Multi-architecture Docker images (linux/amd64, linux/arm64, linux/arm/v7, linux/arm/v6, linux/386)
- Automated macOS application builds (DMG) via GitHub Actions on release tags
- GitHub Releases with automatically attached macOS DMG files
- Build dependencies documentation (requirements-build.txt)
- CONTRIBUTING guide for contributors
- Environment variable toggles for reasoning and web search configuration
- Graceful error handling for ChunkedEncodingError during streaming
- Comprehensive project documentation in CLAUDE.md

### Changed
- Improved OAuth token refresh mechanism
- Enhanced request limits visibility in info command

### Fixed
- ChunkedEncodingError handling during streaming responses

## [Previous Releases]

### Added (Historical)
- Native OpenAI web search capability
- GPT-5-Codex model support
- Reasoning effort as separate models support
- Docker implementation
- Token counting functionality
- Minimal reasoning option for better coding performance
- Response caching to increase usage availability
- Ollama API compatibility
- System prompts support
- Tool/Function calling support
- Vision/Image understanding
- Thinking summaries through thinking tags
- Configurable thinking effort levels (minimal, low, medium, high)
- Configurable reasoning summaries (auto, concise, detailed, none)
- Homebrew tap for macOS installation
- macOS GUI application

### Fixed (Historical)
- Ollama regression issues
- Tool call argument serialization
- Stream legacy mode: include delta.reasoning alongside reasoning_summary
- Token counting in various chat applications
