"""Full role-based audit — admin + supplier."""
import httpx

BASE = "http://localhost:8000"

# ═══ ADMIN ══════════════════════════════════════════════════
r = httpx.post(f"{BASE}/api/auth/login", json={"username":"superadmin","password":"superadmin"})
admin = {"Authorization": f"Bearer {r.json()['access_token']}"}
print("✅ superadmin login")

# Admin creates supplier
r = httpx.post(f"{BASE}/api/admin/suppliers",
    json={"nickname":"完整测试供应商","username":"full_test_1","password":"test123"}, headers=admin)
sid = r.json()["data"]["id"]
print(f"✅ admin创建供应商 #{sid}")

# Admin creates agent under supplier
r = httpx.post(f"{BASE}/api/admin/agents",
    json={"supplier_id": sid, "nickname": "完整测试代理"}, headers=admin)
aid = r.json()["data"]["id"]
print(f"✅ admin创建代理商 #{aid} (supplier={sid})")

# Admin creates API payer under supplier
r = httpx.post(f"{BASE}/api/admin/api-payers",
    json={"supplier_id": sid, "nickname": "完整测试商户"}, headers=admin)
apid = r.json()["data"]["id"]
print(f"✅ admin创建API支付商 #{apid}")

# ═══ SUPPLIER ═══════════════════════════════════════════════
r = httpx.post(f"{BASE}/api/auth/login", json={"username":"full_test_1","password":"test123"})
sup = {"Authorization": f"Bearer {r.json()['access_token']}"}
print(f"✅ supplier login — ref_id={r.json()['reference_id']}")

# Supplier dashboard
r = httpx.get(f"{BASE}/api/merchant/dashboard", headers=sup)
print(f"✅ dashboard: agents={r.json()['data']['agent_count']} payers={r.json()['data']['apayer_count']}")

# Supplier creates agent
r = httpx.post(f"{BASE}/api/merchant/agents", json={"nickname":"自建代理A"}, headers=sup)
print(f"✅ supplier创建代理商: {r.json()['message']}")

# Supplier lists their agents
r = httpx.get(f"{BASE}/api/merchant/agents", headers=sup)
print(f"✅ supplier的代理商: {len(r.json()['data'])} 个")

# Supplier creates API payer
r = httpx.post(f"{BASE}/api/merchant/api-payers", json={"nickname":"自建商户X"}, headers=sup)
print(f"✅ supplier创建API支付商: {r.json()['message']} — Key={r.json()['data']['api_key'][:16]}...")

# Supplier lists their API payers
r = httpx.get(f"{BASE}/api/merchant/api-payers", headers=sup)
print(f"✅ supplier的API支付商: {len(r.json()['data'])} 个")

# Supplier products
r = httpx.get(f"{BASE}/api/merchant/products", headers=sup)
print(f"✅ supplier的货品: {len(r.json()['data'])} 个")

# Supplier wallet
r = httpx.get(f"{BASE}/api/merchant/wallet", headers=sup)
print(f"✅ supplier钱包: balance={r.json()['data']['balance']}")

# Supplier toggle agent status
r = httpx.put(f"{BASE}/api/merchant/agents/{aid}?status=INACTIVE", json={}, headers=sup)
print(f"✅ supplier停用代理商: {r.json()['message']}")

# Supplier toggle API payer status
r = httpx.put(f"{BASE}/api/merchant/api-payers/{apid}?status=INACTIVE", json={}, headers=sup)
print(f"✅ supplier停用API支付商: {r.json()['message']}")

print("\n🎉 完整角色审计通过!")
