"""
Test script to verify statistics collection
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_openai_chat():
    """Test OpenAI chat completions endpoint"""
    print("Testing OpenAI chat completions...")
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "gpt-5",
            "messages": [{"role": "user", "content": "Say 'Hello' in one word"}],
            "stream": False
        }
    )
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Response: {data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')[:50]}")
        print(f"Tokens: {data.get('usage', {})}")
    else:
        print(f"Error: {response.text[:200]}")
    print()

def test_openai_completions():
    """Test OpenAI completions endpoint"""
    print("Testing OpenAI text completions...")
    response = requests.post(
        f"{BASE_URL}/v1/completions",
        json={
            "model": "gpt-5",
            "prompt": "Say 'Hello' in one word",
            "stream": False
        }
    )
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Response: {data.get('choices', [{}])[0].get('text', 'N/A')[:50]}")
        print(f"Tokens: {data.get('usage', {})}")
    else:
        print(f"Error: {response.text[:200]}")
    print()

def test_ollama_chat():
    """Test Ollama chat endpoint"""
    print("Testing Ollama chat...")
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={
            "model": "gpt-5",
            "messages": [{"role": "user", "content": "Say 'Hello' in one word"}],
            "stream": False
        }
    )
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Response: {data.get('message', {}).get('content', 'N/A')[:50]}")
    else:
        print(f"Error: {response.text[:200]}")
    print()

def check_stats():
    """Check collected statistics"""
    print("Checking statistics...")
    response = requests.get(f"{BASE_URL}/api/stats")
    if response.ok:
        stats = response.json()
        print(f"Total requests: {stats.get('total_requests', 0)}")
        print(f"Successful: {stats.get('total_successful', 0)}")
        print(f"Failed: {stats.get('total_failed', 0)}")
        print(f"Total tokens: {stats.get('total_tokens', 0)}")
        print(f"Average response time: {stats.get('avg_response_time', 0):.3f}s")
        print(f"\nRequests by model:")
        for model, count in stats.get('requests_by_model', {}).items():
            print(f"  {model}: {count}")
        print(f"\nRequests by endpoint:")
        for endpoint, count in stats.get('requests_by_endpoint', {}).items():
            print(f"  {endpoint}: {count}")
        print(f"\nTokens by model:")
        for model, tokens in stats.get('tokens_by_model', {}).items():
            print(f"  {model}: {tokens}")
    else:
        print(f"Error: {response.text[:200]}")
    print()

def check_request_history():
    """Check request history"""
    print("Checking request history...")
    response = requests.get(f"{BASE_URL}/api/request-history?limit=10")
    if response.ok:
        data = response.json()
        print(f"Recent requests: {data.get('total_count', 0)}")
        for i, req in enumerate(data.get('requests', [])[:5], 1):
            print(f"\n  Request {i}:")
            print(f"    Time: {req.get('timestamp', 'N/A')}")
            print(f"    Model: {req.get('model', 'N/A')}")
            print(f"    Endpoint: {req.get('endpoint', 'N/A')}")
            print(f"    Success: {req.get('success', False)}")
            print(f"    Tokens: {req.get('total_tokens', 0)}")
            print(f"    Response time: {req.get('response_time', 0):.3f}s")
            if req.get('error'):
                print(f"    Error: {req.get('error', 'N/A')}")
    else:
        print(f"Error: {response.text[:200]}")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("ChatMock Statistics Collection Test")
    print("=" * 60)
    print()

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

    # Run tests
    print("Running test requests...\n")

    test_openai_chat()
    time.sleep(1)

    test_openai_completions()
    time.sleep(1)

    test_ollama_chat()
    time.sleep(1)

    # Check results
    print("=" * 60)
    print("Statistics Results")
    print("=" * 60)
    print()

    check_stats()
    check_request_history()

    print("=" * 60)
    print("Test completed!")
    print("=" * 60)
