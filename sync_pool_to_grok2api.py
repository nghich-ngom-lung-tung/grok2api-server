"""
sync_pool_to_grok2api.py — Đồng bộ toàn bộ token pool vào Grok2API server
────────────────────────────────────────────────────────────────────────────
Đọc tokens từ keys/accounts.txt hoặc data/pool_state.json và import vào Grok2API.

Cách dùng:
    uv run python sync_pool_to_grok2api.py
"""
import sys
import os
import json
import requests
from common import get_base_url, get_admin_token

BASE_URL = get_base_url()
POOL_FILE = "data/pool_state.json"
KEYS_FILE = "keys/accounts.txt"


def get_active_tokens():
    """Đọc SSO tokens từ keys/accounts.txt hoặc data/pool_state.json."""
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
    """Import tất cả token vào Grok2API qua Admin API."""
    tokens = get_active_tokens()
    if not tokens:
        print("[-] Chưa có token nào trong kho.")
        return

    print(f"📦 Tìm thấy {len(tokens)} tokens cần đồng bộ vào grok2api...")
    token_str = "\n".join(tokens)

    admin_jwt = get_admin_token()
    if not admin_jwt:
        print("[❌] Không thể đăng nhập Admin API.")
        return

    headers = {"Authorization": f"Bearer {admin_jwt}"}

    files = {"file": ("tokens.txt", token_str, "text/plain")}

    res = requests.post(
        f"{BASE_URL}/api/admin/v1/accounts/web/import",
        headers=headers,
        files=files,
        timeout=30,
    )
    print("Kết quả import vào grok2api:")
    for line in res.iter_lines():
        if line:
            print(line.decode("utf-8", errors="ignore"))


if __name__ == "__main__":
    sync()
