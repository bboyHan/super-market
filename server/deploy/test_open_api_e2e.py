"""Complete Open API E2E test with self-contained test data creation."""
import httpx
import hashlib
import json

BASE = "http://localhost:8000"
ADM = {"username": "admin", "password": "admin123"}


def md5_sign(params: dict, secret: str) -> str:
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    raw = f"{sorted_params}&key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()


# 1. Admin login
r = httpx.post(f"{BASE}/api/auth/login", json=ADM)
adm_tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {adm_tok}"}
print("[OK] Admin logged in")

# 2. Find an ACTIVE supplier with ACTIVE API payers
r = httpx.get(f"{BASE}/api/admin/suppliers", headers=hs)
suppliers = r.json().get("data", [])
print(f"Found {len(suppliers)} suppliers")

# Find or create a supplier user
target_supplier_id = None
supplier_token = None
for s in suppliers:
    sid = s["id"]
    # Check if we have a user for this supplier
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": f"sup_{sid}", "password": "test123"})
    if r.status_code != 200:
        # Try common names
        for name, pw in [("admin", "admin123"), ("test", "test123")]:
            r2 = httpx.post(f"{BASE}/api/auth/login", json={"username": name, "password": pw})
            if r2.status_code == 200:
                tok = r2.json().get("access_token")
                if tok:
                    prof = httpx.get(f"{BASE}/api/auth/profile", headers={"Authorization": f"Bearer {tok}"})
                    if prof.status_code == 200 and prof.json().get("data", {}).get("role") == "SUPPLIER":
                        supplier_token = tok
                        break
        if supplier_token:
            break
    else:
        supplier_token = r.json()["access_token"]
        break

# If no supplier user found, create one
if not supplier_token:
    import secrets
    uname = f"open_test_{secrets.token_hex(4)}"
    pw = secrets.token_hex(8)
    r = httpx.post(f"{BASE}/api/admin/suppliers",
                   json={"nickname": "OpenAPI测试供应商", "username": uname, "password": pw},
                   headers=hs)
    print(f"Created supplier: {r.json()}")
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": uname, "password": pw})
    supplier_token = r.json()["access_token"]
    # Get supplier id
    prof = httpx.get(f"{BASE}/api/auth/profile", headers={"Authorization": f"Bearer {supplier_token}"})
    target_supplier_id = prof.json().get("data", {}).get("ref_id")

# Get supplier id
prof = httpx.get(f"{BASE}/api/auth/profile", headers={"Authorization": f"Bearer {supplier_token}"})
profile_data = prof.json().get("data", {})
target_supplier_id = profile_data.get("reference_id") or profile_data.get("ref_id")
print(f"[OK] Supplier profile: {profile_data}")

# Authorize products for this supplier
r = httpx.get(f"{BASE}/api/admin/products", headers=hs)
all_products = r.json().get("data", [])
if all_products:
    pid = all_products[0]["id"] if isinstance(all_products[0], dict) else all_products[0][0]
    r = httpx.post(f"{BASE}/api/admin/products/{pid}/authorize-supplier?supplier_id={target_supplier_id}&settlement_price=100", headers=hs)
    authorized_product_id = pid
    print(f"[OK] Authorized product #{pid}: {r.json()}")
else:
    print("[FAIL] No products in system")
    exit(1)

print(f"[OK] Supplier #{target_supplier_id} ready")

# 3. Create agent for this supplier + add inventory
shs = {"Authorization": f"Bearer {supplier_token}"}
r = httpx.post(f"{BASE}/api/merchant/agents", json={"nickname": "openapi_agent"}, headers=shs)
agent = r.json().get("data", {})
agent_id = agent.get("id")
print(f"[OK] Created agent #{agent_id}: {r.json()}")

# Give agent some points (transfer from supplier wallet)
# First, deposit some points via admin
r = httpx.post(f"{BASE}/api/admin/deposits", headers=hs)  # dummy for now
# Use the recharge endpoint
r = httpx.post(f"{BASE}/api/merchant/wallet/recharge?amount=10000", headers=shs)
print(f"[Recharge] {r.json()}")

# Transfer to agent
r = httpx.post(f"{BASE}/api/merchant/wallet/transfer?agent_id={agent_id}&amount=5000", headers=shs)
print(f"[Transfer] {r.json()}")

# Add inventory for known product
r = httpx.post(f"{BASE}/api/terminal/inventory/add",
               json={"agent_id": agent_id, "product_id": int(authorized_product_id), "content": "OPENAPI_TEST_CARD"},
               headers=shs)
print(f"[Add Inventory] {r.json()}")

# 4. Create API payer for this supplier  
r = httpx.post(f"{BASE}/api/merchant/api-payers", json={"nickname": "openapi_test_payer"}, headers=shs)
payer = r.json().get("data", {})
api_key = payer.get("api_key", "")
api_secret = payer.get("api_secret", "")
print(f"[OK] Created API payer: key={api_key[:20]}... secret={api_secret[:20]}...")

# 4. Test product list
params = {"account": api_key}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/products", data=params)
print(f"[Products] {r.json()}")
rj = r.json()
assert rj["code"] == 0, f"Products failed: {rj}"
products = rj.get("data", [])
assert len(products) > 0, "No products available"
print(f"[OK] Products: {len(products)} items")

# 5. Test order create
prod_id = products[0]["product_id"]
client_order_id = f"E2E_{__import__('time').time():.0f}"
notify_url = "https://httpbin.org/post"

params = {"account": api_key, "product_id": prod_id, "quantity": "1",
          "order_id": client_order_id, "notify_url": notify_url}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
print(f"[Create] {r.json()}")
rj = r.json()
assert rj["code"] == 0, f"Create failed: {rj}"
platform_order_id = rj["data"]["platform_order_id"]
assert rj["data"]["status"] == "PENDING"
print(f"[OK] Created {platform_order_id}")

# 6. Test order query
params = {"account": api_key, "order_id": client_order_id}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
rj = r.json()
assert rj["code"] == 0
assert rj["data"]["status"] == "PENDING"
assert rj["data"]["platform_order_id"] == platform_order_id
print(f"[OK] Query: status={rj['data']['status']}")

# 7. Test bad signature
params["sign"] = "bad_signature"
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
assert r.json()["code"] == 40001
print(f"[OK] Bad sig rejected")

# 8. Test duplicate order_id
params = {"account": api_key, "product_id": prod_id, "quantity": "1",
          "order_id": client_order_id, "notify_url": notify_url}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/create", data=params)
assert r.json()["code"] == 40005
print(f"[OK] Duplicate order_id rejected")

# 9. Confirm + Deliver via supplier
shs = {"Authorization": f"Bearer {supplier_token}"}
r = httpx.post(f"{BASE}/api/merchant/orders/{platform_order_id}/confirm", headers=shs)
print(f"[Confirm] {r.json()}")
assert r.json()["code"] == 0

r = httpx.post(f"{BASE}/api/merchant/orders/{platform_order_id}/deliver?delivery_content=E2E_TEST_CARD", headers=shs)
print(f"[Deliver] {r.json()}")
rj = r.json()
assert rj["code"] == 0

# 10. Query after delivery
params = {"account": api_key, "order_id": client_order_id}
params["sign"] = md5_sign(params, api_secret)
r = httpx.post(f"{BASE}/api/open/v1/order/query", data=params)
rj = r.json()
assert rj["code"] == 0
assert rj["data"]["status"] == "SUCCESS", f"Expected SUCCESS, got {rj['data']['status']}"
assert len(rj["data"]["deliveries"]) > 0
print(f"[OK] Full lifecycle: PENDING → SUCCESS, {len(rj['data']['deliveries'])} deliveries")
print(f"[OK] Delivery content: {rj['data']['deliveries'][0]['content']}")

print("\n═══════════════ ALL OPEN API TESTS PASSED ═══════════════")
