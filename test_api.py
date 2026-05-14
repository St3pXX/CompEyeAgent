#!/usr/bin/env python3
"""直连测试 MiMo API"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

base_url = os.getenv('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1').rstrip('/')
url = f'{base_url}/chat/completions'
api_key = os.getenv('MIMO_API_KEY')

if not api_key:
    raise SystemExit('Missing MIMO_API_KEY environment variable.')

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}
data = {
    'model': os.getenv('VERIFIER_MODEL', 'mimo-v2.5-pro'),
    'messages': [{'role': 'user', 'content': 'say hello'}],
    'max_completion_tokens': 50
}

print(f"Testing {url}")
print("Proxy: disabled")

try:
    session = requests.Session()
    session.trust_env = False
    r = session.post(url, json=data, headers=headers, timeout=30)
    print(f'Status: {r.status_code}')
    print(r.text[:800])
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
