# ChatMock Tests

This directory contains test and utility scripts for ChatMock.

## Test Scripts

### Statistics Testing

**`test_stats.py`** - Comprehensive statistics collection test
- Tests all API endpoints (OpenAI chat/completions, Ollama chat)
- Verifies statistics are properly collected and stored
- Checks request history tracking
- Displays collected metrics

**Usage:**
```bash
# Make sure server is running
python chatmock.py serve

# In another terminal
cd tests
python test_stats.py
```

### GPT-5.1 Models Testing

**`test_gpt51.py`** - GPT-5.1 models verification test
- Tests all 3 GPT-5.1 models (gpt-5.1, gpt-5.1-codex, gpt-5.1-codex-mini)
- Verifies functionality on both OpenAI and Ollama endpoints
- Checks token counting and response generation
- Provides detailed test results

**Usage:**
```bash
cd tests
python test_gpt51.py
```

### Experimental Models Testing

**`test_experimental_flag.py`** - Experimental models flag verification
- Tests EXPOSE_EXPERIMENTAL_MODELS flag behavior
- Verifies model visibility with flag on/off
- Checks runtime configuration API

**Usage:**
```bash
cd tests
python test_experimental_flag.py
```

## Utility Scripts

### Statistics Utilities

**`check_stats.py`** - Quick statistics viewer
- Displays current statistics from the dashboard
- Shows requests by model, endpoint, and token usage
- Useful for quick status checks

**Usage:**
```bash
cd tests
python check_stats.py
```

**`check_webui_models.py`** - WebUI models list viewer
- Shows all models available in WebUI API
- Displays model capabilities
- Useful for verifying model configuration

**Usage:**
```bash
cd tests
python check_webui_models.py
```

## Running All Tests

To run all tests sequentially:

```bash
# Start server in background
python chatmock.py serve &

# Wait for server to start
sleep 3

# Run all tests
cd tests
python test_stats.py
python test_gpt51.py
python test_experimental_flag.py
python check_stats.py
python check_webui_models.py
```

## Requirements

All test scripts require:
- ChatMock server running on http://localhost:8000
- `requests` library installed (included in requirements.txt)

## Test Data

Tests will create real API requests and statistics. The statistics are stored in:
- `~/.chatgpt-local/stats.json` (or `$CHATGPT_LOCAL_HOME/stats.json`)

## Cleanup

To reset statistics between tests:
```bash
rm ~/.chatgpt-local/stats.json
```

## Writing New Tests

When adding new test scripts:
1. Follow the naming convention: `test_*.py` or `check_*.py`
2. Include error handling for server connectivity
3. Provide clear output with [OK]/[ERROR] status markers
4. Add documentation to this README

## Troubleshooting

**Server not running:**
```
[ERROR] Cannot connect to server
```
Solution: Start the server with `python chatmock.py serve`

**Authentication errors:**
- Make sure you've logged in: `python chatmock.py login`
- Check your ChatGPT Plus/Pro subscription is active

**Port conflicts:**
- Check if port 8000 is available
- Use `PORT=8001 python chatmock.py serve` to use different port
- Update test scripts to match: `BASE_URL = "http://localhost:8001"`
