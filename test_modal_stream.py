import requests
import json
import time

url = 'https://naveen95190--cris-zira-researcher-ziraresearcher-chat-co-f403d9.modal.run'

print('Waiting for container startup...')
time.sleep(15)

payload = {
    'messages': [{'role': 'user', 'content': 'Say hello in 5 words.'}],
    'max_tokens': 20,
    'temperature': 0.7,
    'stream': True
}

print('Testing streaming...')
resp = requests.post(url, json=payload, stream=True, timeout=120)
print(f'Status: {resp.status_code}')
print(f'Content-Type: {resp.headers.get("content-type", "N/A")}')
print('---')

for line in resp.iter_lines():
    if not line:
        continue
    line = line.decode('utf-8')
    print(line[:120])
