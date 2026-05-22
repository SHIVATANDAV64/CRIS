import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_chat_stream():
    url = f"{BASE_URL}/api/chat/stream"
    payload = {
        "message": "I want a deep understanding of the recent breakthrough of DeepSeek new architecture.",
        "use_reasoning": True,
        "web_search": True
    }
    
    print("Sending streaming query...")
    resp = requests.post(url, json=payload, stream=True)
    
    full_text = ""
    thinking_text = ""
    sources = []
    
    for line in resp.iter_lines():
        if not line:
            continue
        line_str = line.decode("utf-8").strip()
        if line_str.startswith("data:"):
            data_content = line_str[5:].strip()
            if data_content == "[DONE]":
                break
            try:
                data = json.loads(data_content)
                dtype = data.get("type")
                if dtype == "token":
                    token = data.get("token", "")
                    print(token, end="", flush=True)
                    full_text += token
                elif dtype == "thinking":
                    thinking = data.get("content", "")
                    thinking_text += thinking
                elif dtype == "sources":
                    sources = data.get("sources", [])
            except Exception as e:
                pass
                
    print("\n\n=== Streaming Finished ===")
    print(f"\nThinking length: {len(thinking_text)} characters")
    print(f"Response length: {len(full_text)} characters")
    print("\nSources retrieved:")
    for idx, src in enumerate(sources, 1):
        print(f"[{idx}] {src.get('title')} ({src.get('arxiv_id')}) - Type: {src.get('contribution_type', 'Paper')}")

if __name__ == "__main__":
    test_chat_stream()
