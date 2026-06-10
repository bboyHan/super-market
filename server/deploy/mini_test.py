"""Minimal Open API test using supplier #1 which has products."""
import httpx, hashlib, asyncio, json
BASE = "http://localhost:8000"

def md5_sign(params, secret):
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    return hashlib.md5((f"{sorted_params}&key={secret}").encode()).hexdigest()

async def main():
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
    tok = r.json()["access_token"]
    hs = {"Authorization": f"Bearer {tok}"}

    # Supplier #1 API payers
    r = httpx.get(f"{BASE}/api/admin/api-payers?supplier_id=1", headers=hs)
    payers = r.json().get("data", [])
    active = [p for p in payers if p.get("status") == "ACTIVE"]
    
    if not active:
        print("NO ACTIVE PAYERS for supplier #1")
        # Try supplier #2
        r = httpx.get(f"{BASE}/api/admin/api-payers?supplier_id=2", headers=hs)
        active = [p for p in r.json().get("data", []) if p.get("status") == "ACTIVE"]
    
    if not active:
        print("NO ACTIVE PAYERS found anywhere!")
        return
    
    p = active[0]
    print(f"Using payer #{p['id']}: {p['nickname']} (key={p['api_key'][:16]}...)")

    # Test products
    params = {"account": p["api_key"]}
    params["sign"] = md5_sign(params, p["api_secret"])
    try:
        r = httpx.post(f"{BASE}/api/open/v1/products", data=params, timeout=10)
        print(f"Products: {json.dumps(r.json(), ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"Products error: {e}")

asyncio.run(main())
