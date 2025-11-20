"""
Test script to verify GPT-5.1 models are working correctly
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_model(model_name, endpoint_type="openai"):
    """Test a specific model"""
    print(f"\nTesting {model_name} ({endpoint_type})...")

    try:
        if endpoint_type == "openai":
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Say 'Hello from " + model_name + "' in one sentence"}],
                    "stream": False
                },
                timeout=30
            )
        else:  # ollama
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Say 'Hello from " + model_name + "' in one sentence"}],
                    "stream": False
                },
                timeout=30
            )

        if response.ok:
            data = response.json()
            if endpoint_type == "openai":
                content = data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')
                tokens = data.get('usage', {})
                print(f"  [OK] Status: {response.status_code}")
                print(f"  Response: {content[:100]}...")
                print(f"  Tokens: prompt={tokens.get('prompt_tokens', 0)}, completion={tokens.get('completion_tokens', 0)}, total={tokens.get('total_tokens', 0)}")
            else:
                content = data.get('message', {}).get('content', 'N/A')
                print(f"  [OK] Status: {response.status_code}")
                print(f"  Response: {content[:100]}...")
            return True
        else:
            print(f"  [ERROR] Status: {response.status_code}")
            print(f"  Error: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("GPT-5.1 Models Test")
    print("=" * 60)

    # Test health
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.ok:
            print("[OK] Server is running\n")
        else:
            print("[ERROR] Server returned error\n")
            exit(1)
    except Exception as e:
        print(f"[ERROR] Cannot connect to server: {e}")
        print(f"\nMake sure the server is running on {BASE_URL}")
        exit(1)

    gpt51_models = [
        "gpt-5.1",
        "gpt-5.1-codex",
        "gpt-5.1-codex-mini"
    ]

    results = {"openai": {}, "ollama": {}}

    # Test OpenAI endpoint
    print("\n" + "=" * 60)
    print("Testing OpenAI Chat Completions Endpoint")
    print("=" * 60)
    for model in gpt51_models:
        results["openai"][model] = test_model(model, "openai")

    # Test Ollama endpoint
    print("\n" + "=" * 60)
    print("Testing Ollama Chat Endpoint")
    print("=" * 60)
    for model in gpt51_models:
        results["ollama"][model] = test_model(model, "ollama")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    print("\nOpenAI endpoint:")
    for model, success in results["openai"].items():
        status = "[OK]" if success else "[FAILED]"
        print(f"  {status} {model}")

    print("\nOllama endpoint:")
    for model, success in results["ollama"].items():
        status = "[OK]" if success else "[FAILED]"
        print(f"  {status} {model}")

    # Overall result
    all_passed = all(results["openai"].values()) and all(results["ollama"].values())

    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] All GPT-5.1 models are working correctly!")
    else:
        print("[ERROR] Some models failed tests")
    print("=" * 60)
