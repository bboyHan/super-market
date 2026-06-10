"""USDT Deposit E2E test: login → supplier submit → admin confirm → verify wallet."""
import httpx
import json

BASE = "http://localhost:8000"
ADMIN = {"username": "admin", "password": "admin123"}
SUPPLIER = {"username": "full_test_1", "password": "test123"}

def login(creds):
    r = httpx.post(f"{BASE}/api/auth/login", json={"username": creds["username"], "password": creds["password"]})
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    return data["access_token"]

# 1. Admin login
adm_token = login(ADMIN)
print(f"[OK] Admin logged in: token={adm_token[:20]}...")

# 2. Supplier login
sup_token = login(SUPPLIER)
print(f"[OK] Supplier logged in: token={sup_token[:20]}...")

# 3. Check supplier wallet before deposit
headers_sup = {"Authorization": f"Bearer {sup_token}"}
r = httpx.get(f"{BASE}/api/merchant/wallet", headers=headers_sup)
print(f"[Wallet before] {r.json()}")
wallet_before = r.json()["data"]["balance"]

# 4. Submit deposit request
r = httpx.post(f"{BASE}/api/merchant/deposits?amount=5000&tx_hash=0xabc123test_{__import__('time').time():.0f}&remark=test_deposit", headers=headers_sup)
assert r.status_code == 200, f"Deposit submit failed: {r.text}"
dep = r.json()
deposit_id = dep["data"]["deposit_id"]
assert dep["data"]["status"] == "PENDING"
print(f"[OK] Deposit #{deposit_id} submitted: status={dep['data']['status']}")

# 5. Verify deposit appears in supplier's list
r = httpx.get(f"{BASE}/api/merchant/deposits?status=PENDING", headers=headers_sup)
items = r.json()["data"]["items"]
assert any(d["id"] == deposit_id for d in items), "Deposit not found in supplier list"
print(f"[OK] Deposit visible in supplier's deposit list ({len(items)} pending)")

# 6. Admin lists pending deposits
headers_adm = {"Authorization": f"Bearer {adm_token}"}
r = httpx.get(f"{BASE}/api/admin/deposits?status=PENDING", headers=headers_adm)
items = r.json()["data"]["items"]
pending_ids = [d["id"] for d in items]
assert deposit_id in pending_ids, f"Deposit #{deposit_id} not found in admin pending list"
print(f"[OK] Admin sees deposit #{deposit_id} in pending queue ({len(items)} total pending)")

# 7. Admin confirms deposit
r = httpx.post(f"{BASE}/api/admin/deposits/{deposit_id}/confirm?admin_note=approved", headers=headers_adm)
assert r.status_code == 200, f"Confirm failed: {r.text}"
confirm = r.json()
assert confirm["data"]["status"] == "CONFIRMED"
assert confirm["data"]["credited"] == 5000
print(f"[OK] Admin confirmed deposit #{deposit_id}: credited {confirm['data']['credited']} points")

# 8. Verify wallet increased
r = httpx.get(f"{BASE}/api/merchant/wallet", headers=headers_sup)
wallet_after = r.json()["data"]["balance"]
assert wallet_after == wallet_before + 5000, f"Wallet mismatch: {wallet_before}+5000 != {wallet_after}"
print(f"[OK] Wallet updated: {wallet_before} → {wallet_after} (+5000)")

# 9. Verify transaction recorded
r = httpx.get(f"{BASE}/api/merchant/wallet/transactions?limit=5", headers=headers_sup)
txns = r.json()["data"]["items"]
recharge_txns = [t for t in txns if t["type"] == "RECHARGE"]
assert any("USDT充值审核通过" in t.get("remark", "") for t in recharge_txns), "USDT recharge tx not found"
print(f"[OK] Wallet transaction recorded: {len(recharge_txns)} RECHARGE entries")

# 10. Test reject flow
import time
r = httpx.post(f"{BASE}/api/merchant/deposits?amount=3000&tx_hash=0xreject_test_{time.time():.0f}&remark=test_reject", headers=headers_sup)
dep2 = r.json()
dep2_id = dep2["data"]["deposit_id"]
print(f"[OK] Deposit #{dep2_id} submitted for reject test")

r = httpx.post(f"{BASE}/api/admin/deposits/{dep2_id}/reject?admin_note=invalid_tx", headers=headers_adm)
assert r.status_code == 200, f"Reject failed: {r.text}"
print(f"[OK] Admin rejected deposit #{dep2_id}")

# Verify deposit is rejected in supplier's list
r = httpx.get(f"{BASE}/api/merchant/deposits?status=REJECTED", headers=headers_sup)
items = r.json()["data"]["items"]
assert any(d["id"] == dep2_id for d in items), "Rejected deposit not visible"
print(f"[OK] Rejected deposit visible in supplier's rejected list")

# 11. Summary
print("\n═══════════════ ALL TESTS PASSED ═══════════════")
print(f"Supplier wallet: {wallet_before} → {wallet_after}")
print(f"Deposits confirmed: 1, rejected: 1")
print(f"Admin confirm: OK | Reject: OK | Wallet update: OK | Tx record: OK")
