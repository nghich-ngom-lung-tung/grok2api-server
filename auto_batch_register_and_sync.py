import sys, os, time, subprocess, json, requests
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8080"

# 1. Nhận số lượng tài khoản, chế độ Proxy/Direct và Email Provider từ CLI
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
            email_provider = sys.argv[i+1].lower()
            i += 1
    i += 1

mode_str = "🟣 PROXY ROTATION (Xoay IP từ good_proxies.txt)" if use_proxy else "🌐 DIRECT MODE (Mạng trực tiếp)"

print("="*60)
print(f"🚀 BẮT ĐẦU ĐĂNG KÝ TỰ ĐỘNG {total_accounts} TÀI KHOẢN GROK")
print(f"⚙️ Chế độ mạng: {mode_str}")
print(f"📧 Nhà cung cấp Email: {email_provider.upper()}")
print("="*60)

def sync_to_grok2api():
    try:
        # 1. Login Admin
        resp = requests.post(f"{BASE_URL}/api/admin/v1/auth/login", json={"username": "admin", "password": "adminpassword123"}, timeout=10)
        access_token = resp.json()['data']['tokens']['accessToken']
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # 2. Read latest tokens from keys/grok.txt
        tokens_file = os.path.join("keys", "grok.txt")
        if not os.path.exists(tokens_file):
            return
            
        with open(tokens_file, "r", encoding="utf-8") as f:
            tokens = [l.strip() for l in f if l.strip()]
            
        if not tokens:
            return
            
        fresh_tokens = "\n".join(tokens[-total_accounts:])
        
        files = {
            "file": ("tokens.txt", fresh_tokens, "text/plain")
        }
        res = requests.post(f"{BASE_URL}/api/admin/v1/accounts/web/import", headers=headers, files=files, timeout=30)
        print(f"\n[✓] Đã tự động đồng bộ tài khoản mới vào grok2api (Status: {res.status_code})")
    except Exception as e:
        print(f"[!] Lỗi đồng bộ grok2api: {e}")

# 2. Xây dựng lệnh đăng ký
cmd = [
    "uv", "run", "python", "-u", "grok_free.py",
    "--count", str(total_accounts),
    "--email-provider", email_provider,
    "--min-delay", "2",
    "--max-delay", "4"
]

if not use_proxy:
    cmd.append("--direct")

print(f"[*] Đang thực thi tạo {total_accounts} tài khoản...")
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)

for line in process.stdout:
    print(line, end="", flush=True)
    if "✅ ĐĂNG KÝ THÀNH CÔNG!" in line or "✅ SSO:" in line:
        sync_to_grok2api()

process.wait()
print("\n" + "="*60, flush=True)
print(f"✨ HOÀN TẤT ĐĂNG KÝ VÀ NẠP {total_accounts} TÀI KHOẢN VÀO GROK2API!", flush=True)
print("="*60, flush=True)
sync_to_grok2api()
