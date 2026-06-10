"""Full user system audit."""
import httpx

BASE = "http://localhost:8000"

# 1. Login as superadmin
r = httpx.post(f"{BASE}/api/auth/login", json={"username":"superadmin","password":"superadmin"})
admin_tok = r.json()["access_token"]
admin_h = {"Authorization": f"Bearer {admin_tok}"}
print(f"✅ superadmin login — role={r.json()['role']}")

# 2. Create a supplier
r = httpx.post(f"{BASE}/api/admin/suppliers",
    json={"nickname":"供应商A","username":"supplier_a","password":"pass123"}, headers=admin_h)
s = r.json()["data"]
print(f"✅ 创建供应商: {s['nickname']} → 账号={s['username']} 密码={s['password']}")

# 3. Create agent under this supplier
r = httpx.post(f"{BASE}/api/admin/agents",
    json={"supplier_id": s["id"], "nickname": "代理商A1"}, headers=admin_h)
a = r.json()["data"]
print(f"✅ 创建代理商: {a['nickname']} (supplier_id={a['supplier_id']})")

# 4. Create API payer under this supplier
r = httpx.post(f"{BASE}/api/admin/api-payers",
    json={"supplier_id": s["id"], "nickname": "支付商户X"}, headers=admin_h)
p = r.json()["data"]
print(f"✅ 创建API支付商: {p['nickname']} → API Key={p['api_key'][:20]}...")

# 5. Login as the supplier
r = httpx.post(f"{BASE}/api/auth/login", json={"username":"supplier_a","password":"pass123"})
sup_tok = r.json()["access_token"]
sup_h = {"Authorization": f"Bearer {sup_tok}"}
print(f"✅ 供应商A登录 — role={r.json()['role']} ref_id={r.json()['reference_id']}")

# 6. Supplier views their dashboard
r = httpx.get(f"{BASE}/api/merchant/dashboard", headers=sup_h)
print(f"✅ 供应商仪表盘: {r.json()['data']['today_amount']} today")

# 7. Supplier views their agents
r = httpx.get(f"{BASE}/api/merchant/agents", headers=sup_h)
print(f"✅ 供应商看代理商: {len(r.json()['data'])} 个")

# 8. Supplier views their products
r = httpx.get(f"{BASE}/api/merchant/products", headers=sup_h)
print(f"✅ 供应商看货品: {len(r.json()['data'])} 个")

# 9. Supplier views their API channel (same as admin api-payers but filtered)
r = httpx.get(f"{BASE}/api/admin/api-payers", headers=admin_h)
print(f"✅ 全局API支付商: {len(r.json()['data'])} 个")

# 10. List all suppliers with stats
r = httpx.get(f"{BASE}/api/admin/suppliers", headers=admin_h)
for sp in r.json()["data"]:
    print(f"   #{sp['id']} {sp['nickname']} | agents={sp['agent_count']} payers={sp['api_payer_count']} | {sp['status']}")

# 11. Edit supplier
r = httpx.put(f"{BASE}/api/admin/suppliers/1",
    json={"nickname":"测试供应商(已编辑)", "status":"ACTIVE"}, headers=admin_h)
print(f"✅ 编辑供应商: {r.json()['message']}")

# 12. Toggle status
r = httpx.put(f"{BASE}/api/admin/api-payers/1",
    json={"nickname":"商户A(已编辑)", "status":"INACTIVE"}, headers=admin_h)
print(f"✅ 停用API支付商: {r.json()['message']}")

print("\n🎉 用户体系审计完成")
