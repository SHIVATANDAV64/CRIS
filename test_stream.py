import requests
import json

url = 'https://naveen95190--cris-zira-researcher-ziraresearcher-chat-co-f403d9.modal.run'

# Test streaming on root path
print('Test: Streaming on root path...')
payload = {
    'messages': [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'Say hello in 3 words.'}
    ],
    'max_tokens': 50,
    'temperature': 0.7,
    'stream': True
}

headers = {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'
}

try:
    response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
    print(f'Status: {response.status_code}')
    print(f'Content-Type: {response.headers.get("content-type", "N/A")}')
    print('---')
    
    chunk_count = 0
    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode('utf-8')
        print(f'RAW: {line[:120]}')
        chunk_count += 1
        if chunk_count > 15:
            print('... (truncated)')
            break
except Exception as e:
    print(f'Error: {e}')
