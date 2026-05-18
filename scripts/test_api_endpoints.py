import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)

def test_endpoints():
    print("Testing Endpoints...")

    # Test OpenAPI docs
    resp = client.get("/openapi.json")
    if resp.status_code == 200:
        print("[SUCCESS] /openapi.json loaded successfully")
    else:
        print(f"[FAIL] /openapi.json failed: {resp.status_code} - {resp.text}")

    # Test settings
    resp = client.get("/api/settings")
    if resp.status_code == 200:
        print("[SUCCESS] /api/settings loaded successfully")
    else:
        print(f"[FAIL] /api/settings failed: {resp.status_code} - {resp.text}")

    # Test models
    resp = client.get("/api/models")
    if resp.status_code == 200:
        print("[SUCCESS] /api/models loaded successfully")
    else:
        print(f"[FAIL] /api/models failed: {resp.status_code} - {resp.text}")

    # Test sessions list
    resp = client.get("/api/sessions")
    if resp.status_code == 200:
        print("[SUCCESS] /api/sessions loaded successfully")
    else:
        print(f"[FAIL] /api/sessions failed: {resp.status_code} - {resp.text}")

    # Test stats
    resp = client.get("/api/stats")
    if resp.status_code == 200:
        print("[SUCCESS] /api/stats loaded successfully")
    else:
        print(f"[FAIL] /api/stats failed: {resp.status_code} - {resp.text}")

    # Test search (mock query)
    resp = client.get("/api/search?q=test")
    if resp.status_code == 200:
        print("[SUCCESS] /api/search loaded successfully")
    else:
        print(f"[FAIL] /api/search failed: {resp.status_code} - {resp.text}")

    # Test chat endpoint with no query
    resp = client.post("/api/chat", json={"message": "", "use_reasoning": False})
    if resp.status_code == 200:
        print("[SUCCESS] /api/chat (empty query) handled successfully")
    else:
        print(f"[FAIL] /api/chat failed: {resp.status_code} - {resp.text}")


if __name__ == "__main__":
    test_endpoints()
