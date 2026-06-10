"""Check API payer status."""
import httpx
import json

BASE = "http://localhost:8000"

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]

# Get API payers
r = httpx.get(f"{BASE}/api/admin/api-payers", headers={"Authorization": f"Bearer {tok}"})
data = r.json().get("data", [])
if not data:
    print("No API payers found.")
else:
    for p in data:
        print(f"#{p['id']} {p['nickname']:20s} status={p['status']:10s} key={p['api_key'][:20]}...")

# If first one is inactive, activate it
if data:
    p = data[0]
    if p["status"] != "ACTIVE":
        r = httpx.put(f"{BASE}/api/admin/api-payers/{p['id']}?status=ACTIVE",
                      headers={"Authorization": f"Bearer {tok}"}, json={})
        print(f"Activated: {r.json()}")
        print(f"API Key: {p['api_key']}")
        print(f"API Secret: {p['api_secret']}")
    else:
        print(f"Already ACTIVE")
        print(f"API Key: {p['api_key']}")
        print(f"API Secret: {p['api_secret']}")
