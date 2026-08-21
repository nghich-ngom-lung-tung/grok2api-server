"""
auto_batch_register_and_sync.py — Đăng ký hàng loạt tài khoản Grok & tự đồng bộ
─────────────────────────────────────────────────────────────────────────────────
Tạo N tài khoản bằng grok_free.py rồi tự động import vào Grok2API server.

Cách dùng:
    uv run python auto_batch_register_and_sync.py 10 --direct
    uv run python auto_batch_register_and_sync.py 5 --proxy --provider mailtm
"""
import sys
import os
import subprocess
import requests
from common import get_base_url, get_admin_token

BASE_URL = get_base_url()

# ── Đọc tham số CLI ──────────────────────────────────────────────────
total_accounts = 5
use_proxy = False
email_provider = "mailtm"

i = 1
while i < len(sys.argv):
    arg = sys.argv[i]
    if arg.isdigit():
        total_accounts = int(arg)
    elif arg.lower() in ["--proxy", "-p", "proxy"]:
        use_proxy = True
    elif arg.lower() in ["--direct", "-d", "direct"]:
        use_proxy = False
    elif arg.lower() in ["--email-provider", "-e", "--provider"]:
        if i + 1 < len(sys.argv):
            email_provider = sys.argv[i + 1].lower()
            i += 1
    i += 1

mode_str = (
    "🟣 PROXY ROTATION (Xoay IP từ good_proxies.txt)"
    if use_proxy
    else "🌐 DIRECT MODE (Mạng trực tiếp)"
)

print("=" * 60)
print(f"🚀 BẮT ĐẦU ĐĂNG KÝ TỰ ĐỘNG {total_accounts} TÀI KHOẢN GROK")
print(f"⚙️ Chế độ mạng: {mode_str}")
print(f"📧 Nhà cung cấp Email: {email_provider.upper()}")
print("=" * 60)


def sync_to_grok2api():
    """Import các token mới nhất từ keys/grok.txt vào Grok2API server."""
    try:
        token = get_admin_token()
        if not token:
            print("[!] Không lấy được admin token — bỏ qua đồng bộ")
            return

        headers = {"Authorization": f"Bearer {token}"}

        tokens_file = os.path.join("keys", "grok.txt")
        if not os.path.exists(tokens_file):
            return

        with open(tokens_file, "r", encoding="utf-8") as f:
            tokens = [l.strip() for l in f if l.strip()]

        if not tokens:
            return

        fresh_tokens = "\n".join(tokens[-total_accounts:])

        files = {"file": ("tokens.txt", fresh_tokens, "text/plain")}
        res = requests.post(
            f"{BASE_URL}/api/admin/v1/accounts/web/import",
            headers=headers,
            files=files,
            timeout=30,
        )
        print(
            f"\n[✓] Đã tự động đồng bộ tài khoản mới vào grok2api (Status: {res.status_code})"
        )
    except Exception as e:
        print(f"[!] Lỗi đồng bộ grok2api: {e}")


# ── Xây dựng lệnh đăng ký ────────────────────────────────────────────
cmd = [
    "uv", "run", "python", "-u", "grok_free.py",
    "--count", str(total_accounts),
    "--email-provider", email_provider,
    "--min-delay", "2",
    "--max-delay", "4",
]

if not use_proxy:
    cmd.append("--direct")

print(f"[*] Đang thực thi tạo {total_accounts} tài khoản...")
process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    bufsize=1,
)

for line in process.stdout:
    print(line, end="", flush=True)
    if "✅ ĐĂNG KÝ THÀNH CÔNG!" in line or "✅ SSO:" in line:
        sync_to_grok2api()

process.wait()
print("\n" + "=" * 60, flush=True)
print(
    f"✨ HOÀN TẤT ĐĂNG KÝ VÀ NẠP {total_accounts} TÀI KHOẢN VÀO GROK2API!",
    flush=True,
)
print("=" * 60, flush=True)
sync_to_grok2api()
