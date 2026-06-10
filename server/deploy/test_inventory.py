"""Test inventory management + order with inventory check."""
import httpx

BASE = "http://localhost:8000"

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "superadmin", "password": "superadmin"})
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
print("✅ Login")

# 1. Check current inventory
r1 = httpx.get(f"{BASE}/api/terminal/inventory?agent_id=1&limit=5", headers=h)
print(f"📦 Inventory: {r1.json()['data']['total']} items")

# 2. Add inventory for agent 1, product 1
pay_links = [
    "https://pay.jd.com/order/SD20250607001",
    "https://pay.jd.com/order/SD20250607002",
    "JD-CARD-A1B2-C3D4-E5F6",
    "https://pay.taobao.com/order/TB20250607001",
]
r2 = httpx.post(f"{BASE}/api/terminal/inventory/batch",
    json={"agent_id": 1, "product_id": 1, "items": pay_links}, headers=h)
print(f"📥 Batch add: {r2.json()['message']}")

# 3. Check summary
r3 = httpx.get(f"{BASE}/api/terminal/inventory/summary", headers=h)
for s in r3.json()["data"]:
    print(f"   {s['product_name']}: {s['available']} available / {s['total']} total")

# 4. Create order (should have inventory now)
r4 = httpx.post(f"{BASE}/api/admin/simulate/create-order",
    json={"api_payer_id": 1, "product_id": 1, "quantity": 2,
          "client_order_id": "inv-test", "callback_url": "https://test.local/cb"},
    headers=h)
print(f"🛒 Order: {r4.json()['message']} — {r4.json()['data']['status']}")
on = r4.json()["data"]["platform_order_id"]

# 5. Confirm + deliver
r5 = httpx.post(f"{BASE}/api/merchant/orders/{on}/confirm", headers=h)
print(f"✅ Confirm: {r5.json()['message']}")

r6 = httpx.post(f"{BASE}/api/merchant/orders/{on}/deliver", headers=h)
print(f"✅ Deliver: {r6.json()['message']}")

# 6. Verify inventory decreased
r7 = httpx.get(f"{BASE}/api/terminal/inventory/summary", headers=h)
for s in r7.json()["data"]:
    print(f"   {s['product_name']}: {s['available']} available / {s['total']} total")

print("\n🎉 All inventory tests passed!")
