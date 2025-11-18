# ChatMock - Project Overview

## Project Description

ChatMock is an open-source tool that provides OpenAI and Ollama compatible API access powered by your ChatGPT Plus/Pro account. It allows developers to use GPT-5, GPT-5.1, GPT-5-Codex, and other advanced models through their authenticated ChatGPT account without requiring a separate OpenAI API key.

## Key Features

### Model Support
- **GPT-5**: Latest flagship model from OpenAI
- **GPT-5.1**: Enhanced version with improved capabilities
- **GPT-5-Codex**: Specialized model optimized for coding tasks
- **Codex-Mini**: Lightweight variant for faster responses

### Advanced Capabilities
- **Tool/Function Calling**: Support for executing functions and tools during conversations
- **Vision/Image Understanding**: Process and analyze images in conversations
- **Thinking Summaries**: Access to model reasoning through thinking tags
- **Configurable Thinking Effort**: Adjust reasoning depth (minimal, low, medium, high)
- **Web Search**: Native OpenAI web search capability when enabled
- **Streaming Support**: Real-time response streaming
- **Extended Context**: Larger context windows than standard ChatGPT interface

### API Compatibility
- **OpenAI Compatible**: Full compatibility with OpenAI SDK and API format
- **Ollama Compatible**: Works with Ollama-compatible applications
- **Standard Endpoints**: `/v1/chat/completions`, `/v1/models`, etc.

## Architecture

### Core Components

1. **OAuth Authentication Layer** (`chatmock/oauth.py`)
   - Handles ChatGPT account authentication
   - Uses Codex OAuth client for secure access
   - Token management and refresh

2. **API Routes** (`chatmock/routes_openai.py`, `chatmock/routes_ollama.py`)
   - OpenAI-compatible endpoints
   - Ollama-compatible endpoints
   - Request/response transformation

3. **Upstream Handler** (`chatmock/upstream.py`)
   - Communicates with ChatGPT backend
   - Manages streaming responses
   - Error handling and retries

4. **Configuration Management** (`chatmock/config.py`)
   - Environment variable parsing
   - Runtime configuration
   - Default settings

### Technology Stack
- **Python 3.11+**: Core runtime
- **Flask**: Web server framework
- **Docker**: Containerization support
- **OAuth2**: Authentication protocol

## Deployment Options

### 1. Python/Flask Server
Direct execution on your machine with Python:
```bash
python chatmock.py login
python chatmock.py serve
```

### 2. macOS GUI Application
Native macOS application with graphical interface available from GitHub releases.

### 3. Homebrew (macOS)
```bash
brew tap RayBytes/chatmock
brew install chatmock
```

### 4. Docker
Containerized deployment with Docker Compose:
- Persistent authentication storage
- Easy configuration via environment variables
- Support for PUID/PGID for permission management

## Configuration Options

### Reasoning Controls
- `CHATGPT_LOCAL_REASONING_EFFORT`: Control thinking depth (minimal|low|medium|high)
- `CHATGPT_LOCAL_REASONING_SUMMARY`: Reasoning output format (auto|concise|detailed|none)
- `CHATGPT_LOCAL_REASONING_COMPAT`: Compatibility mode (legacy|o3|think-tags|current)
- `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS`: Expose reasoning levels as separate models

### Feature Toggles
- `CHATGPT_LOCAL_ENABLE_WEB_SEARCH`: Enable web search capability
- `VERBOSE`: Enable detailed request/response logging
- `PORT`: Server listening port (default: 8000)

### Advanced Options
- `CHATGPT_LOCAL_HOME`: Authentication data directory
- `CHATGPT_LOCAL_CLIENT_ID`: OAuth client override
- `CHATGPT_LOCAL_DEBUG_MODEL`: Force specific model

## Use Cases

1. **Development Tools**: Integrate ChatGPT models into your development workflow
2. **Alternate Chat UIs**: Use your preferred chat interface with ChatGPT models
3. **Automation**: Build automated workflows using ChatGPT capabilities
4. **Testing**: Test applications against GPT-5 models
5. **Research**: Experiment with different reasoning levels and configurations

## Requirements

- **Active ChatGPT Plus or Pro Account**: Required for API access
- **Python 3.11+**: For running locally
- **Docker** (optional): For containerized deployment
- **Network Access**: To communicate with ChatGPT backend

## Security Considerations

- Credentials stored locally in `CHATGPT_LOCAL_HOME` directory
- OAuth token-based authentication
- No API keys exposed
- Local server for API endpoint (default: 127.0.0.1)

## Limitations

- Requires active, paid ChatGPT account
- Some context may be used by internal instructions
- Rate limits determined by your ChatGPT account tier
- Not officially affiliated with OpenAI

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on contributing to this project.

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## Support

For issues, feature requests, or questions:
- GitHub Issues: [ChatMock Issues](https://github.com/RayBytes/ChatMock/issues)
- Pull Requests welcome for improvements and bug fixes

## Disclaimer

This is an educational project and is not affiliated with or endorsed by OpenAI. Use responsibly and in accordance with OpenAI's terms of service.
