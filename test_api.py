#!/usr/bin/env python3
"""强制禁用代理，直连 MiMo API"""

import os
# 强制清除所有代理相关环境变量
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(var, None)

import requests

url = 'https://api.xiaomimmo.com/v1/models'
headers = {'Authorization': 'Bearer tp-cjrtta91sivhvwqenmic1mfx5y9df8n6jy9ts7671l8f5gxi'}

print(f"Testing direct connection to {url}")
print(f"http_proxy env: {os.environ.get('http_proxy', 'NOT SET')}")

try:
    r = requests.get(url, headers=headers, timeout=15)
    print(f'Status: {r.status_code}')
    print(r.text[:500])
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
