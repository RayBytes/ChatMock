"""
Test script to verify experimental models flag works correctly
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def get_webui_models():
    """Get models from WebUI API"""
    resp = requests.get(f"{BASE_URL}/api/models")
    if resp.ok:
        return [m['id'] for m in resp.json()['models']]
    return []

def get_config():
    """Get current configuration"""
    resp = requests.get(f"{BASE_URL}/api/config")
    if resp.ok:
        return resp.json()
    return {}

def set_experimental_flag(value):
    """Set experimental models flag"""
    resp = requests.post(
        f"{BASE_URL}/api/config",
        json={"expose_experimental_models": value}
    )
    return resp.ok

print("=" * 60)
print("Experimental Models Flag Test")
print("=" * 60)
print()

# Check initial config
print("1. Checking initial configuration...")
config = get_config()
initial_flag = config.get('expose_experimental_models', False)
print(f"   expose_experimental_models: {initial_flag}")
print()

# Get models with flag disabled
print("2. Getting models with experimental flag DISABLED...")
set_experimental_flag(False)
models_disabled = get_webui_models()
print(f"   Models count: {len(models_disabled)}")
print(f"   Models: {', '.join(models_disabled)}")
print()

# Get models with flag enabled
print("3. Getting models with experimental flag ENABLED...")
set_experimental_flag(True)
models_enabled = get_webui_models()
print(f"   Models count: {len(models_enabled)}")
print(f"   Models: {', '.join(models_enabled)}")
print()

# Restore initial state
print("4. Restoring initial configuration...")
set_experimental_flag(initial_flag)
print(f"   Restored to: {initial_flag}")
print()

# Results
print("=" * 60)
print("Results")
print("=" * 60)

if len(models_enabled) == len(models_disabled):
    print("[OK] No experimental models defined - counts match")
    print(f"     Both configurations show {len(models_disabled)} models")
else:
    extra_models = set(models_enabled) - set(models_disabled)
    print("[OK] Experimental models flag working correctly")
    print(f"     With flag OFF: {len(models_disabled)} models")
    print(f"     With flag ON:  {len(models_enabled)} models")
    print(f"     Experimental models: {', '.join(extra_models)}")

print()
print("=" * 60)
print("Test completed!")
print("=" * 60)
