"""Check GPT-5.1 models in WebUI API"""
import requests

resp = requests.get('http://localhost:8000/api/models')
models = resp.json()['models']
gpt51_models = [m for m in models if 'gpt-5.1' in m['id'].lower()]

print('GPT-5.1 models in WebUI API:')
for m in gpt51_models:
    print(f'  - {m["id"]}: {m["name"]}')
    print(f'    Capabilities: {", ".join(m["capabilities"])}')

print(f'\nTotal: {len(gpt51_models)} models')
