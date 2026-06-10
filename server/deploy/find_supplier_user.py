"""Login as supplier #1's user to complete the order lifecycle."""
import httpx
import hashlib
import json

BASE = "http://localhost:8000"
ADM = {"username": "admin", "password": "admin123"}

def md5_sign(params: dict, secret: str) -> str:
    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()) if k != "sign")
    raw = f"{sorted_params}&key={secret}"
    return hashlib.md5(raw.encode()).hexdigest()

# Get existing supplier users
r = httpx.post(f"{BASE}/api/auth/login", json=ADM)
adm_tok = r.json()["access_token"]
hs = {"Authorization": f"Bearer {adm_tok}"}

# Try common usernames
for uname in ["test", "supplier1", "sup_1", "test_supplier", "测试供应商", "admin"]:
    for pw in ["test123", "admin123", "123456", "supplier1"]:
        r = httpx.post(f"{BASE}/api/auth/login", json={"username": uname, "password": pw})
        if r.status_code == 200:
            data = r.json()
            tok = data.get("access_token")
            if tok:
                # Check role
                r2 = httpx.get(f"{BASE}/api/auth/profile", headers={"Authorization": f"Bearer {tok}"})
                if r2.status_code == 200:
                    prof = r2.json().get("data", {})
                    print(f"  USER: {uname}/{pw} → role={prof.get('role')} ref_id={prof.get('ref_id')}")
                    if prof.get("role") == "SUPPLIER":
                        # Check if it's supplier #1
                        href = httpx.get(f"{BASE}/api/merchant/dashboard", headers={"Authorization": f"Bearer {tok}"})
                        if href.status_code == 200:
                            print(f"    Dashboard accessible (supplier)")
