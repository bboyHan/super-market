"""Verify all finance page API endpoints."""
import httpx, json

BASE = "http://localhost:8000"

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {tok}"}

# Test all endpoints that finance page calls
endpoints = [
    "/api/merchant/wallet",
    "/api/merchant/wallet/transactions?limit=50",
    "/api/merchant/deposits?limit=50",
    "/api/merchant/exchange-rate",
    "/api/merchant/deposit-addresses",
]

for ep in endpoints:
    r = httpx.get(f"{BASE}{ep}", headers=hs, timeout=10)
    data = r.json()
    code = data.get("code", data.get("detail", "?"))
    ok = "✅" if code == 0 else "❌"
    print(f"{ok} {ep} → code={code}")

# Also check if merchant dashboard works (for the recent orders shown on finance page)
r = httpx.get(f"{BASE}/api/merchant/dashboard", headers=hs, timeout=10)
print(f"{'✅' if r.json().get('code')==0 else '❌'} /api/merchant/dashboard → code={r.json().get('code')}")
