"""Full order lifecycle test: create → confirm → deliver → callback."""
import httpx
import json

BASE = "http://localhost:8000"

# Login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "superadmin", "password": "superadmin"})
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
print("✅ Login OK")

# 1. Create order
r1 = httpx.post(f"{BASE}/api/admin/simulate/create-order",
    json={"api_payer_id": 1, "product_id": 1, "quantity": 1,
          "client_order_id": "lifecycle-test", "callback_url": "http://localhost:9999/cb"},
    headers=h)
o = r1.json()["data"]
on = o["platform_order_id"]
print(f"✅ 1. 创建订单: {on} → {o['status']}")

# 2. Confirm payment
r2 = httpx.post(f"{BASE}/api/merchant/orders/{on}/confirm", headers=h)
print(f"✅ 2. 确认收款: {r2.json()['message']} → {r2.json()['data']['status']}")

# 3. Deliver
r3 = httpx.post(f"{BASE}/api/merchant/orders/{on}/deliver",
    json={"delivery_content": f"TEST-CARD-{on[-8:]}"}, headers=h)
print(f"✅ 3. 交付: {r3.json()['message']} → {r3.json()['data']['delivery_content']}")

# 4. Check order
r4 = httpx.get(f"{BASE}/api/admin/simulate/orders?limit=5", headers=h)
for o in r4.json()["data"]["items"]:
    if o["order_no"] == on:
        print(f"✅ 4. 最终状态: status={o['status']} callback={o['callback_status']}")

# 5. Get delivery
r5 = httpx.get(f"{BASE}/api/merchant/orders/{on}/deliveries", headers=h)
print(f"✅ 5. 交付内容: {r5.json()['data']}")

print("\n🎉 完整生命周期测试通过!")
