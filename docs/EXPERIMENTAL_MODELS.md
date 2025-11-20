# Experimental Models Support

## Overview

ChatMock supports a generic mechanism for experimental/preview models. This allows testing new models before they are considered production-ready without exposing them to all users by default.

## Configuration

### Environment Variable

Set the `EXPOSE_EXPERIMENTAL_MODELS` environment variable to enable experimental models:

```bash
export EXPOSE_EXPERIMENTAL_MODELS=true
```

### Runtime Configuration

You can also enable experimental models at runtime via the WebUI API:

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"expose_experimental_models": true}'
```

## Adding New Experimental Models

When new experimental models become available, add them to the `model_info` dictionary in `chatmock/routes_webui.py` with the `"experimental": True` flag:

```python
model_info = {
    # ... existing models ...

    "gpt-6-preview": {
        "name": "GPT-6 Preview",
        "description": "Next generation model (experimental preview)",
        "capabilities": ["reasoning", "function_calling", "vision", "web_search"],
        "efforts": ["high", "medium", "low", "minimal"],
        "experimental": True,  # Mark as experimental
    },
}
```

### Required Fields

- `name`: Display name for the model
- `description`: Brief description of the model
- `capabilities`: Array of capabilities (e.g., "reasoning", "function_calling", "vision", "web_search", "coding")
- `efforts`: Array of reasoning effort levels (or empty array if not applicable)
- `experimental`: Boolean flag (set to `true` for experimental models)

## Behavior

### When `EXPOSE_EXPERIMENTAL_MODELS=false` (default)

- Experimental models are **hidden** from:
  - `/api/models` endpoint (WebUI)
  - Model selection in dashboards
  - Documentation

- Experimental models can **still be used** via:
  - Direct API calls to OpenAI endpoints (`/v1/chat/completions`, `/v1/completions`)
  - Direct API calls to Ollama endpoints (`/api/chat`)

### When `EXPOSE_EXPERIMENTAL_MODELS=true`

- All experimental models are **visible** and **listed** in all endpoints
- Users can select experimental models from WebUI dashboards
- Models appear in model listings with their experimental status indicated

## Promoting Models to Production

When an experimental model is ready for production:

1. Remove the `"experimental": True` flag from the model definition in `routes_webui.py`
2. Update the model description to remove "(experimental)" or "(preview)" labels
3. Commit the changes with a note about the model promotion

Example:

```python
# Before (experimental)
"gpt-6-preview": {
    "name": "GPT-6 Preview",
    "description": "Next generation model (experimental preview)",
    "experimental": True,
}

# After (production)
"gpt-6": {
    "name": "GPT-6",
    "description": "Next generation model from OpenAI",
}
```

## Current Status

### Production Models
- `gpt-5` ✓
- `gpt-5.1` ✓
- `gpt-5-codex` ✓
- `gpt-5.1-codex` ✓
- `gpt-5.1-codex-mini` ✓
- `codex-mini` ✓

### Experimental Models
None currently. All models are production-ready.

## Testing Experimental Models

### 1. Enable Experimental Models

```bash
export EXPOSE_EXPERIMENTAL_MODELS=true
python chatmock.py serve
```

### 2. Verify Model Availability

```bash
# Check OpenAI endpoint
curl http://localhost:8000/v1/models | jq '.data[].id'

# Check Ollama endpoint
curl http://localhost:8000/api/tags | jq '.models[].name'

# Check WebUI endpoint
curl http://localhost:8000/api/models | jq '.models[].id'
```

### 3. Test API Calls

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-6-preview",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 4. Check Statistics Collection

After making requests, verify that experimental models are tracked in statistics:

```bash
curl http://localhost:8000/api/stats | jq '.requests_by_model'
```

## Best Practices

1. **Always mark new models as experimental initially** - Even if they seem stable, mark them as experimental for the first release
2. **Test thoroughly before promoting** - Ensure the model works correctly with all features (streaming, function calling, etc.)
3. **Document limitations** - If an experimental model has known limitations, document them in the description
4. **Monitor statistics** - Track usage and error rates for experimental models
5. **Communicate changes** - When promoting a model to production, update release notes and user documentation

## Examples

### Adding a New Experimental Model

```python
# In chatmock/routes_webui.py, add to model_info:
"gpt-6-turbo-preview": {
    "name": "GPT-6 Turbo Preview",
    "description": "Faster variant of GPT-6 (experimental - may have stability issues)",
    "capabilities": ["reasoning", "function_calling"],
    "efforts": ["medium", "low"],
    "experimental": True,
},
```

### Testing the New Model

```bash
# Enable experimental models
export EXPOSE_EXPERIMENTAL_MODELS=true

# Start server
python chatmock.py serve

# Test the model
python -c "
import requests
resp = requests.post('http://localhost:8000/v1/chat/completions', json={
    'model': 'gpt-6-turbo-preview',
    'messages': [{'role': 'user', 'content': 'Test message'}]
})
print(f'Status: {resp.status_code}')
print(f'Response: {resp.json()}')
"
```

## Future Considerations

- Add `experimental_since` date field to track how long models have been in preview
- Add `stability_level` field (e.g., "alpha", "beta", "rc") for more granular control
- Support per-user experimental model access via authentication
- Add telemetry for experimental model usage and error rates
