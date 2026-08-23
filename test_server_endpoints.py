"""
Verification script for FastAPI Server (REST & SSE Streaming) and LangGraph Agent.
Run: python test_server_endpoints.py
"""

import sys
import asyncio
import json
import httpx

API_BASE = "http://localhost:8000"

async def test_health():
    print("\n--- 1. Testing /api/health ---")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_BASE}/api/health", timeout=10.0)
            print(f"Status Code: {r.status_code}")
            print(f"Response: {r.json()}")
            assert r.status_code == 200
            print("✅ Health check passed.")
        except Exception as e:
            print(f"❌ Health check failed: {e}")

async def test_metrics():
    print("\n--- 2. Testing /api/metrics ---")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API_BASE}/api/metrics", timeout=10.0)
            print(f"Status Code: {r.status_code}")
            print(f"Response: {json.dumps(r.json(), indent=2)}")
            assert r.status_code == 200
            print("✅ Metrics check passed.")
        except Exception as e:
            print(f"❌ Metrics check failed: {e}")

async def test_streaming():
    print("\n--- 3. Testing /api/stream (SSE Streaming) ---")
    payload = {
        "query": "How do I troubleshoot a disk full alert?",
        "session_id": "test-session-123",
        "context": {"host": "icinga-master", "service": "disk /"}
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("POST", f"{API_BASE}/api/stream", json=payload) as response:
                print(f"Streaming Status Code: {response.status_code}")
                assert response.status_code == 200
                
                print("Receiving stream chunks:")
                async for chunk in response.aiter_text():
                    for line in chunk.split("\n"):
                        if line.startswith("event:") or line.startswith("data:"):
                            print(f"  {line}")
                            
            print("✅ SSE Streaming test passed.")
        except Exception as e:
            print(f"❌ SSE Streaming test failed: {e}")

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("==================================================")
    print("  FASTAPI AIOPS AGENT — ENDPOINT VERIFICATION")
    print("==================================================")
    asyncio.run(test_health())
    asyncio.run(test_metrics())
    asyncio.run(test_streaming())
