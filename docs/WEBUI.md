# ChatMock WebUI Documentation

## Overview

ChatMock includes a modern web-based dashboard for monitoring, configuration, and management. The WebUI provides real-time insights into your API usage, model information, and system configuration.

## Features

### 1. Dashboard
- **Real-time Statistics**: View total requests, tokens processed, and usage patterns
- **Rate Limit Monitoring**: Visual progress bars showing current usage against ChatGPT Plus/Pro limits
  - 5-hour rolling window limit
  - Weekly limit
  - Automatic reset time display
- **Request Analytics**: Bar charts showing requests by model
- **Usage History**: Track when requests were made

### 2. Models Page
- **Complete Model List**: Browse all available GPT-5 models
- **Model Details**: View descriptions and capabilities for each model
- **Capability Badges**: Quick visual indicators for features like:
  - Reasoning
  - Function calling
  - Vision
  - Web search
  - Coding specialization

### 3. Configuration Page
- **Runtime Configuration**: Adjust settings without restarting the container
- **Reasoning Controls**:
  - Effort level (minimal, low, medium, high)
  - Summary verbosity (auto, concise, detailed, none)
  - Compatibility mode (legacy, o3, think-tags, current)
- **Feature Toggles**:
  - Verbose logging
  - Expose reasoning model variants
  - Default web search enablement
- **Live Updates**: Changes take effect immediately (until container restart)

## Accessing the WebUI

### Local Development
```bash
# Start ChatMock
python chatmock.py serve

# Open browser to:
http://localhost:8000/webui
```

### Docker (Standalone)
```bash
# Start with docker-compose
docker-compose up -d

# Access WebUI at:
http://localhost:8000/webui
```

### Docker with Traefik
```bash
# Start with Traefik integration
docker-compose -f docker-compose.traefik.yml up -d

# Access WebUI at:
https://your-domain.com/webui
```

## Authentication

The WebUI displays authentication status and user information:
- **Authenticated**: Shows email, plan type, and full dashboard
- **Not Authenticated**: Shows instructions for running login command

To authenticate:
```bash
# Docker
docker-compose --profile login up chatmock-login

# Local
python chatmock.py login
```

## API Endpoints

The WebUI uses the following API endpoints (also available for custom integrations):

### Status
```http
GET /api/status
```
Returns authentication status and user information.

### Statistics
```http
GET /api/stats
```
Returns usage statistics and rate limit information.

### Models
```http
GET /api/models
```
Returns list of available models with details.

### Configuration
```http
GET /api/config
POST /api/config
```
Get or update runtime configuration.

Example POST body:
```json
{
  "verbose": true,
  "reasoning_effort": "high",
  "reasoning_summary": "detailed",
  "expose_reasoning_models": true,
  "default_web_search": false
}
```

## Performance

The WebUI is designed for minimal overhead:
- **Single-page application**: No build process required
- **Auto-refresh**: Stats update every 30 seconds when dashboard is active
- **Efficient rendering**: Only active tab is updated
- **Lightweight**: Pure HTML/CSS/JS with no external dependencies

## Customization

### Theming
The WebUI uses CSS variables for easy theming. Edit `/home/user/ChatMock/chatmock/webui/dist/index.html`:

```css
:root {
    --primary: #2563eb;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    /* ... */
}
```

### Adding Custom Features
The WebUI is built with vanilla JavaScript for easy modification:
1. Add new API endpoints in `chatmock/routes_webui.py`
2. Create new rendering functions in the HTML file
3. Add navigation tabs as needed

## Troubleshooting

### WebUI Not Loading
1. Check that the server is running: `docker-compose ps`
2. Verify port 8000 is accessible
3. Check logs: `docker-compose logs chatmock`

### Stats Not Updating
1. Ensure you've made at least one API request
2. Check that `/data` volume has write permissions
3. Verify PUID/PGID match your user

### Authentication Issues
1. Run the login command first
2. Check that tokens are stored in `/data/auth.json`
3. Verify token expiration hasn't occurred

## Security Considerations

- **Local Network Only**: By default, WebUI is not exposed externally
- **No Separate Authentication**: Uses existing ChatGPT OAuth tokens
- **Runtime Config Only**: Configuration changes don't persist to environment
- **CORS Enabled**: API endpoints allow cross-origin requests for flexibility

## Production Deployment

For production use with Traefik:

1. **Configure .env**:
```bash
CHATMOCK_DOMAIN=chatmock.example.com
TRAEFIK_NETWORK=traefik
TRAEFIK_ACME_EMAIL=admin@example.com
```

2. **Start with Traefik**:
```bash
docker-compose -f docker-compose.traefik.yml up -d
```

3. **Access via HTTPS**:
```
https://chatmock.example.com/webui
```

The Traefik setup includes:
- Automatic HTTPS with Let's Encrypt
- HTTP to HTTPS redirect
- CORS headers
- Health checks
- Load balancing ready

## Browser Support

The WebUI supports all modern browsers:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

## Future Enhancements

Planned features:
- Historical usage charts
- Export statistics to CSV/JSON
- Model comparison tools
- Request history viewer
- Cost estimation calculator
- Multi-user management
