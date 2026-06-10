"""Quick check - find a supplier with products."""
import httpx
import json
import hashlib

BASE = "http://localhost:8000"

def md5_sign(params: dict, secret: str) -> str:
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    raw = f"{sorted_params}&key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()

# Admin login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {tok}"}

# Check supplier #1 (测试供应商) - it had products earlier
for sid in [1, 8, 13, 14]:
    r = httpx.get(f"{BASE}/api/admin/products?supplier_id={sid}", headers=hs)
    prods = r.json().get("data", [])
    r2 = httpx.get(f"{BASE}/api/admin/api-payers?supplier_id={sid}", headers=hs)
    payers = r2.json().get("data", [])
    active_payers = [p for p in payers if p.get("status") == "ACTIVE"]
    print(f"Supplier #{sid}: products={len(prods)}, active_payers={len(active_payers)}")
    if prods and active_payers:
        payer = active_payers[0]
        params = {"account": payer["api_key"]}
        params["sign"] = md5_sign(params, payer["api_secret"])
        r3 = httpx.post(f"{BASE}/api/open/v1/products", data=params)
        print(f"  → OpenAPI products: {r3.json()}")
