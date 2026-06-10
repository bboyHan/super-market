"""Test agent creation with login credentials."""
import httpx, json

BASE = "http://localhost:8000"

r = httpx.post(f"{BASE}/api/auth/login", json={"username": "superadmin", "password": "superadmin"})
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# Create agent
r2 = httpx.post(f"{BASE}/api/admin/agents",
    json={"supplier_id": 8, "nickname": "agent-w-login"}, headers=h, timeout=10)
d = r2.json()["data"]
print(f"✅ Agent: {d['username']} / {d['password']}")

# Login as agent
r3 = httpx.post(f"{BASE}/api/auth/login",
    json={"username": d["username"], "password": d["password"]}, timeout=10)
print(f"✅ Agent login: role={r3.json()['role']}")

print("🎉 Agent can log in!")
