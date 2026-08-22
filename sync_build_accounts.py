"""
sync_build_accounts.py — Tự động nạp toàn bộ tài khoản Grok Build OAuth vào Grok2API
────────────────────────────────────────────────────────────────────────────────────
Đọc toàn bộ file xai-*.json trong thư mục keys/auths/ và import vào Grok2API server.

Cách dùng:
    uv run python sync_build_accounts.py
"""
import os
import sys
import json
import time
import requests
from common import get_base_url, get_admin_token

BASE_URL = get_base_url()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_DIR = os.path.join(SCRIPT_DIR, "keys", "auths")

print("=" * 65)
print("🚀 ĐỒNG BỘ TÀI KHOẢN GROK BUILD OAUTH VÀO GROK2API SERVER")
print("=" * 65)

token = get_admin_token()
if not token:
    print("[❌] Server Grok2API chưa được bật hoặc sai mật khẩu Admin.")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

if not os.path.exists(AUTH_DIR):
    print(f"[-] Thư mục {AUTH_DIR} chưa tồn tại.")
    sys.exit(0)

auth_files = [f for f in os.listdir(AUTH_DIR) if f.startswith("xai-") and f.endswith(".json")]
if not auth_files:
    print(f"[-] Chưa có file OAuth nào trong {AUTH_DIR}. Hãy chạy `uv run python sso_to_cpa.py --all` trước!")
    sys.exit(0)

print(f"[*] Tìm thấy {len(auth_files)} tài khoản Grok Build cần nạp...")

total_created = 0
total_updated = 0
total_failed = 0

for idx, fn in enumerate(auth_files, 1):
    fpath = os.path.join(AUTH_DIR, fn)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            
        files = {"file": (fn, content, "application/json")}
        r = requests.post(f"{BASE_URL}/api/admin/v1/accounts/import", headers=headers, files=files, timeout=30)
        if r.status_code in (200, 201):
            print(f"  [{idx}/{len(auth_files)}] [✓] Đã nạp thành công: {fn}")
            total_created += 1
        else:
            print(f"  [{idx}/{len(auth_files)}] [!] Lỗi nạp {fn} (HTTP {r.status_code}): {r.text[:100]}")
            total_failed += 1
    except Exception as e:
        print(f"  [{idx}/{len(auth_files)}] [!] Lỗi kết nối {fn}: {e}")
        total_failed += 1

print("\n" + "=" * 65)
print(f"✨ HOÀN TẤT ĐỒNG BỘ: {total_created} THÀNH CÔNG | {total_failed} THẤT BẠI")
print("=" * 65)
