"""Open API E2E test: verify signature flow, order create, order query."""
import httpx
import hashlib
import json

BASE = "http://localhost:8000"

def md5_sign(params: dict, secret: str) -> str:
    """MD5 sign per vbox-gin spec."""
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    raw = f"{sorted_params}&key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()


# 1. Admin login - get api_key and api_secret from api_payer list
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
adm_token = r.json()["access_token"]
print(f"[OK] Admin logged in")

# Get an API payer with credentials
r = httpx.get(f"{BASE}/api/admin/api-payers", headers={"Authorization": f"Bearer {adm_token}"})
payers = r.json()["data"]
if not payers:
    print("[FAIL] No API payers found. Create one first.")
    exit(1)

payer = payers[0]
api_key = payer["api_key"]
api_secret = payer["api_secret"]
print(f"[OK] Using API payer: {payer['nickname']} (key={api_key[:16]}...)")

# 2. Test product list
params = {"account": api_key}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
print(f"[Products] {r.json()}")
rj = r.json()
assert rj["code"] == 0, f"Products failed: {rj}"
products = rj.get("data", [])
if not products:
    print("[WARN] No products found. May not be able to test order creation.")
else:
    print(f"[OK] Products listed: {len(products)} items")

# 3. Test order create
if products:
    prod_id = products[0]["product_id"]
    client_order_id = f"TEST_{__import__('time').time():.0f}"
    params = {
        "account": api_key,
        "product_id": prod_id,
        "quantity": "1",
        "order_id": client_order_id,
        "notify_url": "https://httpbin.org/post",
    }
    params["sign"] = md5_sign(params, api_secret)
    r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
    print(f"[Create Order] {r.json()}")
    rj = r.json()
    assert rj["code"] == 0, f"Create order failed: {rj}"
    platform_order_id = rj["data"]["platform_order_id"]
    assert rj["data"]["status"] == "PENDING"
    print(f"[OK] Order created: {platform_order_id} (status=PENDING)")

    # 4. Test order query
    params = {
        "account": api_key,
        "order_id": client_order_id,
    }
    params["sign"] = md5_sign(params, api_secret)
    r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
    print(f"[Query Order] {r.json()}")
    rj = r.json()
    assert rj["code"] == 0, f"Query order failed: {rj}"
    assert rj["data"]["status"] == "PENDING"
    assert rj["data"]["platform_order_id"] == platform_order_id
    print(f"[OK] Order queried: status={rj['data']['status']}")

    # 5. Test bad signature
    params["sign"] = "bad_signature"
    r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
    rj = r.json()
    assert rj["code"] == 40001, f"Bad signature should return 40001: {rj}"
    print(f"[OK] Bad signature correctly rejected (code={rj['code']})")

    # 6. Test duplicate order_id
    params = {
        "account": api_key,
        "product_id": prod_id,
        "quantity": "1",
        "order_id": client_order_id,
        "notify_url": "https://httpbin.org/post",
    }
    params["sign"] = md5_sign(params, api_secret)
    r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
    rj = r.json()
    assert rj["code"] == 40005, f"Duplicate order_id should return 40005: {rj}"
    print(f"[OK] Duplicate order_id correctly rejected (code={rj['code']})")

    # 7. Deliver the order via supplier, then query
    # Login as supplier to confirm + deliver
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": "full_test_1", "password": "test123"})
    sup_tok = r.json()["access_token"]
    hs = {"Authorization": f"Bearer {sup_tok}"}

    # Confirm
    r = httpx.post(f"{BASE}/api/merchant/orders/{platform_order_id}/confirm", headers=hs)
    print(f"[Confirm] {r.json()}")

    # Deliver  
    r = httpx.post(f"{BASE}/api/merchant/orders/{platform_order_id}/deliver?delivery_content=OPENAPI_TEST_CARD", headers=hs)
    print(f"[Deliver] {r.json()}")
    rj = r.json()
    assert rj["code"] == 0, f"Deliver failed: {rj}"

    # Query again - should show SUCCESS with deliveries
    params = {"account": api_key, "order_id": client_order_id}
    params["sign"] = md5_sign(params, api_secret)
    r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
    print(f"[Query After Deliver] {r.json()}")
    rj = r.json()
    assert rj["code"] == 0
    assert rj["data"]["status"] == "SUCCESS", f"Expected SUCCESS, got {rj['data']['status']}"
    assert len(rj["data"]["deliveries"]) > 0, f"Expected deliveries"
    print(f"[OK] Full lifecycle: PENDING → CONFIRMED → SUCCESS (deliveries: {len(rj['data']['deliveries'])})")

print("\n═══════════════ ALL TESTS PASSED ═══════════════")
