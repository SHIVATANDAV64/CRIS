import requests
import json

url = 'https://naveen95190--cris-zira-researcher-ziraresearcher-chat-co-f403d9.modal.run'

payload = {
    'messages': [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': 'What is 2+2?'}
    ],
    'max_tokens': 100,
    'temperature': 0.7,
    'stream': True
}

print('Testing streaming with full output...')
resp = requests.post(url, json=payload, stream=True, timeout=120)
print(f'Status: {resp.status_code}')
print(f'Content-Type: {resp.headers.get("content-type", "N/A")}')
print('---')

full_content = ""
for line in resp.iter_lines():
    if not line:
        continue
    line = line.decode('utf-8')
    print(f'RAW: {line}')
    
    if line.startswith('data: '):
        data_str = line[6:]
        if data_str.strip() == '[DONE]':
            break
        try:
            data = json.loads(data_str)
            delta = data.get('choices', [{}])[0].get('delta', {})
            content = delta.get('content', '')
            if content:
                full_content += content
        except:
            pass

print('\n--- FULL CONTENT ---')
print(full_content)
