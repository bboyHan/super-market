"""Quick test admin endpoints."""
import httpx

BASE = "http://localhost:8000"

# Login as superadmin
r = httpx.post(f"{BASE}/api/auth/login",
    json={"username": "superadmin", "password": "superadmin"})
print(f"Login: {r.status_code}")
if r.status_code != 200:
    # Try admin
    r = httpx.post(f"{BASE}/api/auth/login",
        json={"username": "admin", "password": "admin123"})
    print(f"Login(admin): {r.status_code}")

tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

# List suppliers
r2 = httpx.get(f"{BASE}/api/admin/suppliers", headers=h)
print(f"Suppliers: {r2.status_code} count={len(r2.json().get('data',[]))}")

# List api payers
r3 = httpx.get(f"{BASE}/api/admin/api-payers", headers=h)
print(f"API Payers: {r3.status_code} count={len(r3.json().get('data',[]))}")

# List agents
r4 = httpx.get(f"{BASE}/api/admin/agents", headers=h)
print(f"Agents: {r4.status_code} count={len(r4.json().get('data',[]))}")

# List products
r5 = httpx.get(f"{BASE}/api/admin/products", headers=h)
print(f"Products: {r5.status_code} count={len(r5.json().get('data',[]))}")

# Simulate order
r6 = httpx.post(f"{BASE}/api/admin/simulate/create-order",
    json={"api_payer_id": 1, "product_id": 1, "quantity": 1,
          "client_order_id": "sim-test-001", "callback_url": "https://test.local/cb"},
    headers=h)
print(f"Sim Order: {r6.status_code} — {r6.json().get('message','FAIL')[:60]}")

# List sim orders
r7 = httpx.get(f"{BASE}/api/admin/simulate/orders", headers=h)
print(f"Sim Orders: {r7.status_code} count={len(r7.json()['data']['items'])}")

print("\n✅ All tests completed")
