"""
auto_batch_register_and_sync.py — Đăng ký tài khoản Grok + Tự động đúc OAuth + Đồng bộ
──────────────────────────────────────────────────────────────────────────────────────
Tự động đăng ký N tài khoản Grok (Direct hoặc Proxy), sau đó:
1. Đồng bộ tài khoản Web SSO vào Grok2API Server (phục vụ tạo ảnh)
2. Tự động đúc tài khoản sang Grok Build OAuth (phục vụ chat grok-4.5/4.6 và vĩnh viễn)
3. Đồng bộ tài khoản Grok Build OAuth vào Grok2API Server

Cách dùng:
    uv run python auto_batch_register_and_sync.py 1 --proxy
    uv run python auto_batch_register_and_sync.py 5 --direct
    uv run python auto_batch_register_and_sync.py 10 --proxy --provider mailtm
"""
import sys
import os
import subprocess
import time
import requests
import common  # noqa: F401
from common import get_base_url, get_admin_token

BASE_URL = get_base_url()

# ── Đọc tham số CLI ──────────────────────────────────────────────────
total_accounts = 1
threads = None  # None = Tự động tính toán luồng tối ưu
use_proxy = False
email_provider = "mailtm"
no_oauth = False

i = 1
while i < len(sys.argv):
    arg = sys.argv[i]
    if arg.isdigit():
        total_accounts = int(arg)
    elif arg.lower() in ["--threads", "-t"]:
        if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            threads = int(sys.argv[i + 1])
            i += 1
    elif arg.lower() in ["--proxy", "-p", "proxy"]:
        use_proxy = True
    elif arg.lower() in ["--direct", "-d", "direct"]:
        use_proxy = False
    elif arg.lower() in ["--email-provider", "-e", "--provider"]:
        if i + 1 < len(sys.argv):
            email_provider = sys.argv[i + 1].lower()
            i += 1
    elif arg.lower() in ["--no-oauth", "--skip-oauth"]:
        no_oauth = True
    i += 1

# ── Tự động tính toán số luồng thông minh nếu không chỉ định ───────────
is_auto_threads = False
if threads is None or threads <= 0:
    is_auto_threads = True
    if total_accounts <= 1:
        threads = 1
    elif use_proxy:
        threads = min(total_accounts, 5 if total_accounts >= 8 else 4 if total_accounts >= 4 else total_accounts)
    else:
        threads = min(total_accounts, 4 if total_accounts >= 8 else 3 if total_accounts >= 3 else 2)

mode_str = (
    "🟣 PROXY ROTATION (Xoay IP từ good_proxies.txt)"
    if use_proxy
    else "🌐 DIRECT MODE (Mạng trực tiếp)"
)

thread_str = f"{threads} (⚡ Tự động tối ưu theo số nick & mạng)" if is_auto_threads else str(threads)

print("=" * 65)
print(f"🚀 BẮT ĐẦU QUY TRÌNH ĐĂNG KÝ VÀ TẠO OAUTH CHO {total_accounts} TÀI KHOẢN")
print(f"⚡ Số luồng song song: {thread_str}")
print(f"⚙️ Chế độ mạng: {mode_str}")
print(f"📧 Nhà cung cấp Email: {email_provider.upper()}")
print(f"💎 Tự động đúc OAuth: {'BỎ QUA' if no_oauth else 'BẬT (Khuyên dùng)'}")
print("=" * 65)


def sync_web_to_grok2api():
    """Import các token mới nhất từ keys/grok.txt vào Grok2API server (Web Pool)."""
    try:
        token = get_admin_token()
        if not token:
            print("[!] Không lấy được admin token — bỏ qua đồng bộ Web")
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
            f"[✓] Đã đồng bộ tài khoản Web SSO vào Grok2API (Status: {res.status_code})"
        )
    except Exception as e:
        print(f"[!] Lỗi đồng bộ Web grok2api: {e}")


def convert_and_sync_oauth():
    """Tự động đúc toàn bộ tài khoản mới sang OAuth và nạp vào Grok2API Build Pool."""
    if no_oauth:
        return

    print("\n" + "-" * 65)
    print("💎 BƯỚC 2: TỰ ĐỘNG ĐÚC TÀI KHOẢN MỚI SANG GROK BUILD OAUTH...")
    print("-" * 65)
    
    # 1. Chạy sso_to_cpa.py cho các tài khoản chưa có OAuth
    cmd_oauth = ["uv", "run", "python", "-u", "sso_to_cpa.py", "--all"]
    proc_oauth = subprocess.run(cmd_oauth, text=True, encoding="utf-8", errors="replace")
    
    # 2. Chạy sync_build_accounts.py để nạp vào Grok2API
    print("\n" + "-" * 65)
    print("💎 BƯỚC 3: ĐỒNG BỘ TÀI KHOẢN OAUTH VÀO GROK2API BUILD POOL...")
    print("-" * 65)
    cmd_sync = ["uv", "run", "python", "-u", "sync_build_accounts.py"]
    proc_sync = subprocess.run(cmd_sync, text=True, encoding="utf-8", errors="replace")


# ── BƯỚC 1: Xây dựng lệnh và thực thi đăng ký tài khoản ─────────────
cmd = [
    "uv", "run", "python", "-u", "grok_free.py",
    "--count", str(total_accounts),
    "--threads", str(threads),
    "--email-provider", email_provider,
    "--min-delay", "1",
    "--max-delay", "3",
]

if not use_proxy:
    cmd.append("--direct")

print(f"\n[*] Đang khởi chạy tiến trình đăng ký {total_accounts} tài khoản...")
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

process.wait()

print("\n" + "=" * 65, flush=True)
print(f"🎉 ĐĂNG KÝ HOÀN TẤT! ĐANG TIẾN HÀNH ĐỒNG BỘ TOÀN DIỆN...", flush=True)
print("=" * 65, flush=True)

# Đồng bộ Web SSO
sync_web_to_grok2api()

# Đúc và đồng bộ OAuth Build
convert_and_sync_oauth()

print("\n" + "=" * 65, flush=True)
print(f"✨ TẤT CẢ QUY TRÌNH ĐÃ HOÀN TẤT 100%! TÀI KHOẢN ĐÃ SẴN SÀNG SỬ DỤNG!", flush=True)
print("=" * 65, flush=True)
