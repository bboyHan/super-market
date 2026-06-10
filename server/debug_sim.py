"""Debug sim order creation."""
import httpx
import traceback

BASE = "http://localhost:8000"

# Login
r = httpx.post(f"{BASE}/api/auth/login",
    json={"username": "superadmin", "password": "superadmin"})
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

# Create sim order
try:
    r2 = httpx.post(f"{BASE}/api/admin/simulate/create-order",
        json={"api_payer_id": 1, "product_id": 1, "quantity": 1,
              "client_order_id": "sim-test-001", "callback_url": "https://test.local/cb"},
        headers=h)
    print(f"Status: {r2.status_code}")
    print(f"Body: {r2.text[:1000]}")
except Exception as e:
    traceback.print_exc()
