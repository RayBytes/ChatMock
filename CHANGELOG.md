# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Support for GPT-5.1 models
- Docker support with PUID and PGID environment variables for running container with different user credentials
- GitHub Actions workflow for automated Docker image builds and publishing to GitHub Container Registry
- Pre-built Docker images available at `ghcr.io/raybytes/chatmock:latest`
- `docker-compose.registry.yml` for easy deployment using pre-built images
- Multi-architecture Docker images (linux/amd64, linux/arm64)
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
