"""Direct Open API test using an existing supplier with agents."""
import httpx
import hashlib

BASE = "http://localhost:8000"


def md5_sign(params: dict, secret: str) -> str:
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    raw = f"{sorted_params}&key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()


# 1. Login admin
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
tok = r.json()["access_token"]
print(f"[OK] Admin logged in")

# 2. List suppliers and find one with agents + api_payers
r = httpx.get(f"{BASE}/api/admin/suppliers", headers={"Authorization": f"Bearer {tok}"})
suppliers = r.json().get("data", [])
print(f"Suppliers: {len(suppliers)}")

# Use supplier #8 which has agents
TARGET_SUPPLIER_ID = 8
print(f"Using supplier #{TARGET_SUPPLIER_ID}")

# 3. Find supplier's API payer
r = httpx.get(f"{BASE}/api/admin/api-payers?supplier_id={TARGET_SUPPLIER_ID}", headers={"Authorization": f"Bearer {tok}"})
payers = r.json().get("data", [])
print(f"API payers for supplier #{TARGET_SUPPLIER_ID}: {len(payers)}")

# If no payer, create one
if not payers:
    # Need supplier user token
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "full_test_1", "password": "test123"})
    sup_tok = r.json()["access_token"]
    r = httpx.post(f"{BASE}/api/merchant/api-payers", json={"nickname": "direct_test_payer"},
                   headers={"Authorization": f"Bearer {sup_tok}"})
    payer = r.json().get("data", {})
    api_key = payer.get("api_key", "")
    api_secret = payer.get("api_secret", "")
    print(f"Created API payer: key={api_key[:20]}...")
else:
    # Filter to only ACTIVE payers
    active_payers = [p for p in payers if p.get('status') == 'ACTIVE']
    if not active_payers:
        print(f"[FAIL] No active API payers for supplier #{TARGET_SUPPLIER_ID}")
        exit(1)
    payer = active_payers[0]
    api_key = payer["api_key"]
    api_secret = payer["api_secret"]
    print(f"Active API payer: {payer['nickname']} (key={api_key[:20]}...)")

# 4. Test products list
params = {"account": api_key}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
data = r.json().get("data") or []
print(f"\n[Products] code={r.json()['code']} items={len(data)}")

products = r.json().get("data") or []
if not products:
    print("[FAIL] No products - need authorization + inventory")
    exit(1)

# 5. Create order
prod = products[0]
client_order_id = f"DIRECT_{__import__('time').time():.0f}"
params = {"account": api_key, "product_id": prod["product_id"], "quantity": "1",
          "order_id": client_order_id, "notify_url": "https://httpbin.org/post"}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
print(f"\n[Create] {r.json()}")
rj = r.json()
assert rj["code"] == 0, f"Create failed: {rj}"
order_no = rj["data"]["platform_order_id"]
print(f"  Order: {order_no} status={rj['data']['status']}")

# 6. Query order
params = {"account": api_key, "order_id": client_order_id}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
print(f"\n[Query] code={r.json()['code']} status={r.json()['data']['status']}")
assert r.json()["data"]["status"] == "PENDING"

# 7. Bad signature
params["sign"] = "BAD"
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
print(f"\n[Bad Sig] code={r.json()['code']} (expected 40001)")
assert r.json()["code"] == 40001

# 8. Duplicate order_id
params = {"account": api_key, "product_id": prod["product_id"], "quantity": "1",
          "order_id": client_order_id, "notify_url": "https://httpbin.org/post"}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
print(f"\n[Duplicate] code={r.json()['code']} (expected 40005)")
assert r.json()["code"] == 40005

# 9. Nonexistent order
params = {"account": api_key, "order_id": "NONEXISTENT_ORDER"}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
print(f"\n[Not Found] code={r.json()['code']} (expected 40402)")
assert r.json()["code"] == 40402

# 10. Nonexistent account
params = {"account": "sk_fake_key"}
params["sign"] = md5_sign(params, "fake_secret")
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
print(f"\n[Bad Account] code={r.json()['code']} (expected 40004)")
assert r.json()["code"] == 40004

print("\n═══════════════ ALL TESTS PASSED ═══════════════")
