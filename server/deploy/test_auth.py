"""Test auth + wallet endpoints."""
import httpx
import json

BASE = "http://localhost:8000"

# 1. Login
r = httpx.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
assert r.status_code == 200, f"Login failed: {r.text}"
data = r.json()
tok = data["access_token"]
print(f"✅ Login OK — role={data['role']}")
print(f"   Token: {tok[:40]}...")

headers = {"Authorization": f"Bearer {tok}"}

# 2. Profile
r2 = httpx.get(f"{BASE}/api/auth/profile", headers=headers)
print(f"✅ Profile: {r2.status_code} — {r2.json()}")

# 3. Wallet before
r3 = httpx.get(f"{BASE}/api/merchant/wallet", headers=headers)
before = r3.json()
print(f"✅ Wallet before: balance={before['data']['balance']}")

# 4. Recharge (POST with JSON body)
r4 = httpx.post(f"{BASE}/api/merchant/wallet/recharge",
    json={"amount": 20000, "remark": "USDT充值测试"},
    headers=headers)
print(f"✅ Recharge: {r4.status_code} — {r4.json()}")

# 5. Wallet after recharge
r5 = httpx.get(f"{BASE}/api/merchant/wallet", headers=headers)
after_recharge = r5.json()
print(f"✅ Wallet after recharge: balance={after_recharge['data']['balance']}")

# 6. Transfer to agent
r6 = httpx.post(f"{BASE}/api/merchant/wallet/transfer?agent_id=1&amount=3000", headers=headers)
print(f"✅ Transfer: {r6.status_code} — {r6.json()}")
after = r6.json()

# 7. Wallet after transfer
r7 = httpx.get(f"{BASE}/api/merchant/wallet", headers=headers)
print(f"✅ Wallet after transfer: balance={r7.json()['data']['balance']}")

# 8. Transaction history
r8 = httpx.get(f"{BASE}/api/merchant/wallet/transactions", headers=headers)
txns = r8.json()
print(f"✅ Transactions: {len(txns['data']['items'])} records")
for t in txns['data']['items'][:3]:
    print(f"   {t['type']:15s} | {t['amount']:>8} | {t['balance_after']:>8} | {t['remark'][:40]}")

print("\n🎉 All tests passed!")
