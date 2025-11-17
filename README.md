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

  <p><b>Production-ready OpenAI & Ollama compatible API powered by your ChatGPT plan.</b></p>
  <p>Use your ChatGPT Plus/Pro account to call OpenAI models from code or alternate chat UIs.</p>
  <p><i>Now with high-performance server, web dashboard, and automatic HTTPS support.</i></p>
  <br>
</div>

> **⚠️ Fork Notice**: This is a personal fork of [RayBytes/ChatMock](https://github.com/RayBytes/ChatMock) maintained for personal use only. For feature requests, bug reports, and general support, please visit the [original repository](https://github.com/RayBytes/ChatMock) and contact the original author.

## 🚀 What's New

### Performance Improvements
- **⚡ 3-5x Faster**: Gunicorn with gevent workers (200-500+ RPS vs 50 RPS)
- **🔄 High Concurrency**: Handle 1000+ concurrent connections
- **📈 Production-Ready**: Battle-tested WSGI server with automatic worker management

### Web Dashboard
- **📊 Real-time Statistics**: Monitor usage, rate limits, and analytics
- **⚙️ Configuration UI**: Change settings via web interface
- **🔍 Model Browser**: Explore all available models and capabilities
- **Access**: http://localhost:8000/webui

### Traefik Integration
- **🔒 Automatic HTTPS**: Let's Encrypt SSL certificates
- **🌐 Reverse Proxy**: Production-ready deployment
- **⚖️ Load Balancing**: Horizontal scaling support

📚 **[Complete Documentation](./docs/README.md)** | 🎨 **[WebUI Guide](./docs/WEBUI.md)** | 🚀 **[Production Setup](./docs/PRODUCTION.md)** | 🔒 **[Traefik Guide](./docs/TRAEFIK.md)**

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

### Docker (Recommended)

**Quick Start:**
```bash
# 1. Clone repository
git clone https://github.com/thebtf/ChatMock.git
cd ChatMock

# 2. Copy environment file
cp .env.example .env

# 3. Login with ChatGPT account
docker-compose --profile login up chatmock-login

# 4. Start server
docker-compose up -d

# 5. Access WebUI
# Open http://localhost:8000/webui in your browser
```

**Production Deployment with Traefik (Automatic HTTPS):**
```bash
# Configure domain in .env
echo "CHATMOCK_DOMAIN=chatmock.example.com" >> .env
echo "TRAEFIK_ACME_EMAIL=admin@example.com" >> .env

# Deploy with Traefik
docker-compose -f docker-compose.traefik.yml up -d

# Access at https://chatmock.example.com/webui
```

📖 **[Complete Docker Documentation](https://github.com/RayBytes/ChatMock/blob/main/DOCKER.md)** | 🚀 **[Production Guide](./docs/PRODUCTION.md)** | 🔒 **[Traefik Setup](./docs/TRAEFIK.md)**

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

# Web Dashboard

ChatMock now includes a modern web dashboard for monitoring and configuration.

**Access the WebUI:**
- **Local**: http://localhost:8000/webui
- **Production**: https://your-domain.com/webui

**Features:**
- 📊 **Real-time Statistics**: View total requests, tokens, and usage patterns
- 📈 **Rate Limit Monitoring**: Visual progress bars for 5-hour and weekly limits
- 📉 **Analytics Charts**: Requests by model and date
- 🎨 **Model Browser**: Explore all available models with capabilities
- ⚙️ **Configuration Management**: Change settings via UI (runtime only)
- 🔐 **Authentication Status**: View your ChatGPT account info and plan

**API Endpoints** (also available for custom integrations):
- `GET /api/status` - Authentication and user info
- `GET /api/stats` - Usage statistics and rate limits
- `GET /api/models` - Available models with details
- `GET /api/config` - Current configuration
- `POST /api/config` - Update runtime settings

📖 **[WebUI Documentation](./docs/WEBUI.md)**

# Performance

### Benchmarks (4 CPU cores, 8GB RAM)

| Configuration | Requests/Sec | Avg Latency | P95 Latency | Memory |
|--------------|--------------|-------------|-------------|---------|
| Flask Dev Server | 50 | 100ms | 200ms | 150MB |
| Gunicorn (4 workers) | 200 | 80ms | 150ms | 600MB |
| Gunicorn (8 workers) | 350 | 60ms | 120ms | 1.2GB |
| Gunicorn (16 workers) | 500 | 50ms | 100ms | 2.4GB |

**Production Configuration:**
```bash
USE_GUNICORN=1              # Enable Gunicorn (default)
GUNICORN_WORKERS=8          # Number of worker processes
```

📊 **[Production Deployment Guide](./docs/PRODUCTION.md)**

# What's supported

- Tool/Function calling
- Vision/Image understanding
- Thinking summaries (through thinking tags)
- Thinking effort
- Web search (OpenAI native)
- High-performance production server
- Real-time monitoring dashboard
- Automatic HTTPS with Traefik

## Notes & Limits

- Requires an active, paid ChatGPT account.
- Some context length might be taken up by internal instructions (but they dont seem to degrade the model) 
- Use responsibly and at your own risk. This project is not affiliated with OpenAI, and is a educational exercise.

# Supported models
- `gpt-5`
- `gpt-5.1`
- `gpt-5-codex`
- `codex-mini`

# Configuration

ChatMock can be configured via environment variables (Docker) or command-line parameters (Python).

## Quick Configuration

### Via Environment Variables (Docker)

Copy `.env.example` to `.env` and customize:

```bash
# Server
PORT=8000
USE_GUNICORN=1                    # Enable production server
GUNICORN_WORKERS=4                # Number of workers

# Reasoning
CHATGPT_LOCAL_REASONING_EFFORT=medium      # minimal|low|medium|high
CHATGPT_LOCAL_REASONING_SUMMARY=auto       # auto|concise|detailed|none
CHATGPT_LOCAL_REASONING_COMPAT=think-tags  # legacy|o3|think-tags|current

# Features
CHATGPT_LOCAL_ENABLE_WEB_SEARCH=false      # Enable web search
CHATGPT_LOCAL_EXPOSE_REASONING_MODELS=false # Expose reasoning as models
VERBOSE=false                              # Enable verbose logging

# Traefik (Production)
CHATMOCK_DOMAIN=chatmock.example.com
TRAEFIK_ACME_EMAIL=admin@example.com
```

📖 **[Complete .env.example Reference](./.env.example)**

### Via Web Dashboard

Access http://localhost:8000/webui to change settings in real-time:
- Reasoning effort and summary
- Web search enablement
- Verbose logging
- Model exposure

**Note**: WebUI changes are runtime only and reset on restart. For persistent changes, update environment variables.

### Via Command Line (Python)

```bash
python chatmock.py serve \
  --reasoning-effort high \
  --reasoning-summary detailed \
  --enable-web-search \
  --expose-reasoning-models
```

All parameters: `python chatmock.py serve --help`

## Configuration Options

### Server Configuration

- **`PORT`** - Server port (default: 8000)
- **`USE_GUNICORN`** - Enable Gunicorn for production (default: 1)
- **`GUNICORN_WORKERS`** - Number of worker processes (default: CPU × 2 + 1)
- **`VERBOSE`** - Enable verbose request/response logging

### Thinking Controls

- **`CHATGPT_LOCAL_REASONING_EFFORT`** (minimal|low|medium|high)
  - Controls computational effort for reasoning
  - Higher effort = slower but potentially smarter responses
  - Default: `medium`

- **`CHATGPT_LOCAL_REASONING_SUMMARY`** (auto|concise|detailed|none)
  - Controls how reasoning summaries are presented
  - `none` provides fastest responses
  - Default: `auto`

- **`CHATGPT_LOCAL_REASONING_COMPAT`** (legacy|o3|think-tags|current)
  - Controls reasoning output format
  - `think-tags`: Returns in message text with thinking tags
  - `legacy`: Returns in separate reasoning field
  - Default: `think-tags`

### Feature Toggles

- **`CHATGPT_LOCAL_ENABLE_WEB_SEARCH`** - Enable web search tool by default
- **`CHATGPT_LOCAL_EXPOSE_REASONING_MODELS`** - Expose reasoning levels as separate models (e.g., gpt-5-high, gpt-5-low)
- **`CHATGPT_LOCAL_DEBUG_MODEL`** - Force specific model for all requests

### Web Search Usage

Enable web search globally:
```bash
CHATGPT_LOCAL_ENABLE_WEB_SEARCH=true
```

Or per-request via API:
```json
{
  "model": "gpt-5",
  "messages": [{"role":"user","content":"Find current METAR rules"}],
  "responses_tools": [{"type": "web_search"}],
  "responses_tool_choice": "auto"
}
```

Supported tools:
- `{"type": "web_search"}` - Standard web search
- `{"type": "web_search_preview"}` - Preview mode

Tool choice: `"auto"` (let model decide) or `"none"` (disable)

### Production Settings

For optimal production performance:

```bash
# High performance
USE_GUNICORN=1
GUNICORN_WORKERS=8
CHATGPT_LOCAL_REASONING_EFFORT=medium
CHATGPT_LOCAL_REASONING_SUMMARY=auto

# Fastest responses
USE_GUNICORN=1
GUNICORN_WORKERS=16
CHATGPT_LOCAL_REASONING_EFFORT=minimal
CHATGPT_LOCAL_REASONING_SUMMARY=none
```

📊 **[Performance Tuning Guide](./docs/PRODUCTION.md)**

## Notes

- **Fastest responses**: Set `reasoning_effort=minimal` and `reasoning_summary=none`
- **Context size**: Larger than regular ChatGPT interface
- **Thinking tags**: Use `reasoning_compat=legacy` to avoid thinking tags in response text
- **Model variants**: Enable `expose_reasoning_models` for easy model picker selection in chat apps

📚 **[Complete Documentation](./docs/README.md)**

# Deployment Options

ChatMock supports multiple deployment strategies for different use cases:

## 1. Local Development (Python)

Simple Python server for local testing:
```bash
python chatmock.py serve
# Access: http://localhost:8000
```

## 2. Docker (Recommended)

Production-ready deployment with Gunicorn:
```bash
docker-compose up -d
# Access: http://localhost:8000
# WebUI: http://localhost:8000/webui
```

**Features:**
- ⚡ High-performance Gunicorn server
- 🔄 Automatic worker management
- 📦 Persistent data storage
- 🔧 Easy configuration via .env

## 3. Docker with Traefik (Production)

Full production stack with automatic HTTPS:
```bash
docker-compose -f docker-compose.traefik.yml up -d
# Access: https://chatmock.example.com
# WebUI: https://chatmock.example.com/webui
```

**Features:**
- 🔒 Automatic SSL/TLS certificates (Let's Encrypt)
- 🌐 Reverse proxy with health monitoring
- ⚖️ Load balancing ready
- 📊 Traefik dashboard integration

🔒 **[Traefik Setup Guide](./docs/TRAEFIK.md)**

## 4. Kubernetes

Scale horizontally with Kubernetes:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chatmock
spec:
  replicas: 3
  # ... see docs/PRODUCTION.md for complete example
```

**Features:**
- 📈 Horizontal auto-scaling
- 🏥 Health checks and liveness probes
- 🔄 Rolling updates
- 📊 Resource limits and monitoring

🚀 **[Complete Production Guide](./docs/PRODUCTION.md)**

## Comparison

| Method | Performance | Complexity | Best For |
|--------|-------------|------------|----------|
| Python | Low | Simple | Development |
| Docker | High | Easy | Production (single server) |
| Traefik | High | Medium | Production (HTTPS) |
| Kubernetes | Very High | Advanced | Enterprise / High-scale |

# Documentation

Complete guides for all aspects of ChatMock:

- 📚 **[Documentation Index](./docs/README.md)** - Start here
- 🎨 **[WebUI Guide](./docs/WEBUI.md)** - Dashboard features and API
- 🚀 **[Production Deployment](./docs/PRODUCTION.md)** - Performance tuning and scaling
- 🔒 **[Traefik Integration](./docs/TRAEFIK.md)** - Automatic HTTPS setup
- 📖 **[Docker Instructions](https://github.com/RayBytes/ChatMock/blob/main/DOCKER.md)** - Docker basics
- ⚙️ **[.env Reference](./.env.example)** - All configuration options

# Troubleshooting

### WebUI not loading?
1. Verify server is running: `docker-compose ps`
2. Check logs: `docker-compose logs chatmock`
3. Ensure port 8000 is accessible

### Performance issues?
1. Increase workers: `GUNICORN_WORKERS=8`
2. Check resources: `docker stats chatmock`
3. See [Performance Guide](./docs/PRODUCTION.md)

### SSL certificate issues?
1. Verify DNS points to server
2. Check Traefik logs: `docker logs traefik`
3. See [Traefik Guide](./docs/TRAEFIK.md)

For more help, check the [documentation](./docs/README.md) or [open an issue](https://github.com/RayBytes/ChatMock/issues).

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)




