"""Check which supplier owns API payer #1 and get its credentials."""
import httpx
import json

BASE = "http://localhost:8000"

r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {tok}"}

# Get API payers
r = httpx.get(f"{BASE}/api/admin/api-payers", headers=hs)
payers = r.json().get("data", [])
for p in payers:
    print(f"API Payer #{p['id']}: {p['nickname']:20s} supplier_id={p['supplier_id']} supplier={p['supplier_name']}")

# Get suppliers
r = httpx.get(f"{BASE}/api/admin/suppliers", headers=hs)
suppliers = r.json().get("data", [])
for s in suppliers:
    print(f"Supplier #{s['id']}: {s['nickname']:20s} status={s['status']}")
