import sys, os, time, json, requests
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8080"
POOL_FILE = "data/pool_state.json"
KEYS_FILE = "keys/accounts.txt"

def get_admin_token():
    resp = requests.post(f"{BASE_URL}/api/admin/v1/auth/login", json={"username": "admin", "password": "adminpassword123"}, timeout=10)
    return resp.json()['data']['tokens']['accessToken']

def get_active_tokens():
    tokens = []
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("----")
                if len(parts) >= 3:
                    tokens.append(parts[2].strip())
    if not tokens and os.path.exists(POOL_FILE):
        with open(POOL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in data.items():
                sso = v.get("sso") or k
                if sso:
                    tokens.append(sso)
    return list(set(tokens))

def sync():
    tokens = get_active_tokens()
    if not tokens:
        print("[-] Chưa có token nào trong kho.")
        return
    
    print(f"📦 Tìm thấy {len(tokens)} tokens cần đồng bộ vào grok2api...")
    token_str = "\n".join(tokens)
    
    admin_jwt = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_jwt}"}
    
    files = {
        "file": ("tokens.txt", token_str, "text/plain")
    }
    
    res = requests.post(f"{BASE_URL}/api/admin/v1/accounts/web/import", headers=headers, files=files, timeout=30)
    print("Kết quả import vào grok2api:")
    for line in res.iter_lines():
        if line:
            print(line.decode('utf-8', errors='ignore'))

if __name__ == "__main__":
    sync()
