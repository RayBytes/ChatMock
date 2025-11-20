"""Check current statistics"""
import requests
import json

resp = requests.get('http://localhost:8000/api/stats')
data = resp.json()

print('Current statistics:')
print(f'  Total requests: {data["total_requests"]}')
print(f'  Total successful: {data["total_successful"]}')
print(f'  Total failed: {data["total_failed"]}')
print(f'  Total tokens: {data["total_tokens"]}')
print(f'  Average response time: {data["avg_response_time"]:.3f}s')
print()

print('Requests by model:')
for model, count in sorted(data['requests_by_model'].items()):
    print(f'  {model}: {count}')
print()

print('Tokens by model:')
for model, tokens in sorted(data['tokens_by_model'].items()):
    print(f'  {model}: {tokens["total"]} tokens (prompt={tokens["prompt"]}, completion={tokens["completion"]})')
print()

print('Requests by endpoint:')
for endpoint, count in sorted(data['requests_by_endpoint'].items()):
    print(f'  {endpoint}: {count}')
