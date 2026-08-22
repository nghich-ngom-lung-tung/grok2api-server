"""
sso_to_cpa.py — Chuyển đổi SSO sang Grok Build OAuth ĐA LUỒNG SONG SONG
───────────────────────────────────────────────────────────────────────
Chuyển đổi hàng loạt tài khoản Web SSO thành OAuth Token (access_token + refresh_token)
- Hỗ trợ chạy ĐA LUỒNG SONG SONG (3 - 5 trình duyệt chạy đồng thời)
- Tự động vượt Cloudflare Turnstile WAF bằng DrissionPage (auto_port độc lập)
- Tự động xóa OneTrust banner và bấm Allow trên trang Grok Build
- Tự động lấy Auth Code và đổi lấy Access Token + Refresh Token
- Tự động lưu file keys/auths/xai-*.json và NẠP NGAY VÀO SERVER GROK2API

Cách dùng:
    uv run python sso_to_cpa.py --all
    uv run python sso_to_cpa.py --all --threads 4
    uv run python sso_to_cpa.py --count 10 --threads 3
"""
import json
import os
import sys
import time
import shutil
import hashlib
import base64
import secrets
import urllib.parse
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

import common  # noqa: F401
from common import get_base_url, get_admin_token
from DrissionPage import ChromiumPage, ChromiumOptions

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_URL = get_base_url()

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
REDIRECT_URI = "http://127.0.0.1:56121/callback"
TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
AUTHORIZE_URL = "https://auth.x.ai/oauth2/authorize"
SCOPE = "openid profile email offline_access grok-cli:access api:access"

KEYS_DIR = os.path.join(SCRIPT_DIR, "keys")
AUTH_DIR = os.path.join(KEYS_DIR, "auths")
os.makedirs(AUTH_DIR, exist_ok=True)


def load_accounts():
    """Đọc danh sách tài khoản từ keys/accounts.txt."""
    acc_file = os.path.join(KEYS_DIR, "accounts.txt")
    if not os.path.exists(acc_file):
        return []
    accounts = []
    with open(acc_file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 3:
                accounts.append({"email": parts[0], "password": parts[1], "sso": parts[2]})
    return accounts


def sync_single_to_server(file_path):
    """Tự động nạp 1 tài khoản Grok Build trực tiếp vào Grok2API Server."""
    try:
        token = get_admin_token()
        if not token:
            return False
        headers = {"Authorization": f"Bearer {token}"}
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        fn = os.path.basename(file_path)
        files = {"file": (fn, content, "application/json")}
        r = requests.post(f"{BASE_URL}/api/admin/v1/accounts/import", headers=headers, files=files, timeout=15)
        return r.status_code in (200, 201)
    except Exception:
        return False


def sso_to_cpa(sso_token, email=""):
    """Quy trình chuyển đổi SSO cookie thành OAuth access_token + refresh_token."""
    safe_email = email.replace("@", "_").replace(".", "_")

    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": SCOPE,
        "state": secrets.token_urlsafe(16),
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.auto_port()

    temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome", f"mint_{safe_email}_{int(time.time()*1000)%100000}")
    os.makedirs(temp_dir, exist_ok=True)
    co.set_argument(f"--user-data-dir={temp_dir}")

    page = None
    code = None
    try:
        page = ChromiumPage(co)
        page.get("https://accounts.x.ai", timeout=30)
        time.sleep(1)
        page.set.cookies({"name": "sso", "value": sso_token, "domain": ".x.ai", "path": "/"})
        page.set.cookies({"name": "sso-rw", "value": sso_token, "domain": ".x.ai", "path": "/"})

        page.get(auth_url, timeout=30)
        time.sleep(3)

        # 1. Xóa bỏ hoàn toàn lớp phủ Cookie banner bằng JS
        page.run_js('''
        var b1 = document.getElementById("onetrust-consent-sdk"); if(b1) b1.remove();
        var b2 = document.getElementById("onetrust-banner-sdk"); if(b2) b2.remove();
        var b3 = document.querySelector(".onetrust-pc-dark-filter"); if(b3) b3.remove();
        ''')
        time.sleep(0.5)

        # 2. Bấm nút Allow trực tiếp
        btn_allow = page.ele("text:Allow") or page.ele("tag:button@@text():Allow")
        if btn_allow:
            btn_allow.click(by_js=True)
            time.sleep(2.5)

        # 3. Quét lấy code từ các input text hoặc URL (chờ tối đa 10s)
        for _ in range(10):
            if "code=" in page.url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(page.url).query)
                code = parsed.get("code", [None])[0]
                if code:
                    break

            for inp in page.eles("tag:input@@type=text"):
                v = (inp.value or "").strip()
                if len(v) > 30 and " " not in v and v != CLIENT_ID:
                    code = v
                    break
            if code:
                break
            time.sleep(1)

    except Exception as e:
        print(f"  [{email}] [!] Lỗi thao tác trình duyệt: {e}")
        return None
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    if not code:
        print(f"  [{email}] ❌ Không lấy được Auth Code (Cookie hết hạn hoặc bị từ chối)")
        return None

    code = code.strip()
    try:
        r = requests.post(TOKEN_ENDPOINT, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        }, timeout=30)
    except Exception as e:
        print(f"  [{email}] ❌ Lỗi kết nối đổi Token: {e}")
        return None

    if r.status_code != 200:
        print(f"  [{email}] ❌ Đổi Token thất bại: {r.status_code} {r.text[:120]}")
        return None

    data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        print(f"  [{email}] ❌ Không có access_token trong phản hồi: {json.dumps(data)[:120]}")
        return None

    print(f"  [{email}] 🎉 Đúc token Grok Build OAuth thành công! (Hạn: {data.get('expires_in', 21600)}s)")
    return {
        "access_token": access_token,
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 21600),
        "id_token": data.get("id_token", ""),
        "token_type": data.get("token_type", "Bearer"),
    }


def save_auth(email, cpa_data):
    """Lưu file xai-*.json chuẩn và TỰ ĐỘNG NẠP VÀO SERVER GROK2API."""
    safe_email = email.replace("@", "_").replace(".", "_")
    path = os.path.join(AUTH_DIR, f"xai-{safe_email}.json")
    now = time.time()
    expires_in = cpa_data.get("expires_in", 21600)
    record = {
        "type": "xai",
        "auth_kind": "oauth",
        "access_token": cpa_data["access_token"],
        "refresh_token": cpa_data["refresh_token"],
        "token_type": cpa_data.get("token_type", "Bearer"),
        "expires_in": expires_in,
        "expired": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + expires_in)),
        "last_refresh": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "email": email,
        "base_url": "https://cli-chat-proxy.grok.com/v1",
        "token_endpoint": TOKEN_ENDPOINT,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "disabled": False,
        "mint_method": "pkce",
        "protocol_flow": "pkce",
        "headers": {
            "X-XAI-Token-Auth": "xai-grok-cli",
            "x-grok-client-version": "0.2.93",
            "x-grok-client-identifier": "grok-shell",
        },
    }
    if cpa_data.get("id_token"):
        record["id_token"] = cpa_data["id_token"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    
    synced = sync_single_to_server(path)
    if synced:
        print(f"  [{email}] [✓] Đã nạp thành công vào Server Grok2API! 🚀")
    return path


def process_account_task(acc_info, idx, total):
    """Hàm xử lý cho 1 worker thread."""
    email = acc_info["email"]
    sso = acc_info["sso"]
    print(f"[{idx}/{total}] ⚡ Đang đúc OAuth: {email}")
    res = sso_to_cpa(sso, email)
    if res:
        save_auth(email, res)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Chuyển đổi SSO -> Grok Build OAuth ĐA LUỒNG")
    parser.add_argument("--sso", help="SSO token đơn lẻ")
    parser.add_argument("--email", help="Email tương ứng")
    parser.add_argument("--all", action="store_true", help="Chuyển đổi toàn bộ tài khoản chưa có OAuth")
    parser.add_argument("--count", type=int, default=0, help="Số lượng tài khoản cần chuyển đổi")
    parser.add_argument("--threads", "-t", type=int, default=0, help="Số luồng trình duyệt (0 = Tự động tính toán)")
    args = parser.parse_args()

    if args.sso:
        email = args.email or "unknown"
        result = sso_to_cpa(args.sso, email)
        if result:
            save_auth(email, result)
        else:
            print("❌ Chuyển đổi thất bại")
            sys.exit(1)
        return

    if args.all or args.count > 0:
        accounts = load_accounts()
        if not accounts:
            print("[!] Không tìm thấy tài khoản nào trong keys/accounts.txt")
            return

        existing = set()
        for fn in os.listdir(AUTH_DIR):
            if fn.startswith("xai-") and fn.endswith(".json"):
                try:
                    with open(os.path.join(AUTH_DIR, fn), encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("email"):
                        existing.add(d["email"])
                except Exception:
                    pass

        pending = [a for a in accounts if a["email"] not in existing]
        if args.count > 0:
            pending = pending[:args.count]

        # ── Tự động tính toán số luồng thông minh nếu không chỉ định ───────
        is_auto_threads = False
        threads = args.threads
        if threads is None or threads <= 0:
            is_auto_threads = True
            if len(pending) <= 1:
                threads = 1
            elif len(pending) >= 8:
                threads = 4
            elif len(pending) >= 4:
                threads = 3
            else:
                threads = 2
        else:
            threads = max(1, min(threads, len(pending) if pending else 1, 5))

        thread_str = f"{threads} (⚡ Tự động tối ưu theo số acc & RAM máy)" if is_auto_threads else str(threads)

        print("=" * 65)
        print(f"🚀 BẮT ĐẦU CHUYỂN ĐỔI SANG GROK BUILD OAUTH (ĐA LUỒNG SONG SONG)")
        print(f"📊 Tổng acc: {len(accounts)} | Đã có OAuth: {len(existing)} | Cần đúc: {len(pending)}")
        print(f"⚡ Số luồng trình duyệt song song: {thread_str}")
        print("=" * 65)

        if not pending:
            print("🎉 Tất cả tài khoản đều đã có OAuth! Không cần chuyển đổi thêm.")
            return

        start_time = time.time()
        success_count = 0

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {
                executor.submit(process_account_task, acc, idx, len(pending)): acc
                for idx, acc in enumerate(pending, 1)
            }
            for future in as_completed(futures):
                try:
                    if future.result():
                        success_count += 1
                except Exception as e:
                    print(f"[!] Lỗi thread: {e}")

        total_time = round(time.time() - start_time, 1)
        print("\n" + "=" * 65)
        print(f"✨ HOÀN TẤT: {success_count}/{len(pending)} TÀI KHOẢN ĐÃ ĐÚC OAUTH & NẠP VÀO SERVER THÀNH CÔNG!")
        print(f"⏱️ Tổng thời gian xử lý: {total_time}s")
        print("=" * 65)


if __name__ == "__main__":
    main()