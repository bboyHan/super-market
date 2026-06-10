"""Full Open API test using supplier #1 which has products + agents."""
import httpx, hashlib, json
BASE = "http://localhost:8000"

def md5_sign(params, secret):
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    return hashlib.md5((f"{sorted_params}&key={secret}").encode()).hexdigest()

# 1. Login admin
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {tok}"}
print("[OK] Admin logged in")

# 2. Get supplier #1's ACTIVE API payer
r = httpx.get(f"{BASE}/api/admin/api-payers?supplier_id=1", headers=hs)
active = [p for p in r.json().get("data", []) if p.get("status") == "ACTIVE"]
if not active:
    print("[FAIL] No active API payer for supplier #1")
    exit(1)
payer = active[0]
ak, sec = payer["api_key"], payer["api_secret"]
print(f"[OK] Using payer: {payer['nickname']}")

# 3. Products
params = {"account": ak}
params["sign"] = md5_sign(params, sec)
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
assert r.json()["code"] == 0
products = r.json().get("data", [])
assert len(products) > 0
pid = products[0]["product_id"]
print(f"[OK] Products: {len(products)} (using #{pid})")

# 4. Create order
client_oid = f"TEST_{__import__('time').time():.0f}"
params = {"account": ak, "product_id": pid, "quantity": "1", "order_id": client_oid}
params["sign"] = md5_sign(params, sec)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
rj = r.json()
assert rj["code"] == 0, f"Create failed: {rj}"
order_no = rj["data"]["platform_order_id"]
print(f"[OK] Order created: {order_no} (PENDING)")

# 5. Query order
params = {"account": ak, "order_id": client_oid}
params["sign"] = md5_sign(params, sec)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
assert r.json()["code"] == 0
assert r.json()["data"]["status"] == "PENDING"
print(f"[OK] Query: PENDING")

# 6. Bad signature
params2 = {"account": ak, "order_id": client_oid, "sign": "bad"}
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params2)
assert r.json()["code"] == 40001
print(f"[OK] Bad sig: 40001")

# 7. Duplicate order
params = {"account": ak, "product_id": pid, "quantity": "1", "order_id": client_oid}
params["sign"] = md5_sign(params, sec)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
assert r.json()["code"] == 40005
print(f"[OK] Duplicate: 40005")

# 8. Non-existent order
params = {"account": ak, "order_id": "NONEXISTENT_ORDER_ID_12345"}
params["sign"] = md5_sign(params, sec)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
assert r.json()["code"] == 40402, f"Expected 40402, got {r.json()}"
print(f"[OK] Non-existent: 40402")

# 9. Bad account
params = {"account": "fake_key", "sign": "fake"}
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
assert r.json()["code"] == 40004
print(f"[OK] Bad account: 40004")

print("\n═══════════════ ALL TESTS PASSED ═══════════════")
print(f"Coverage: products ✓ create ✓ query ✓ bad-sig ✓ duplicate ✓ not-found ✓ bad-account ✓")
