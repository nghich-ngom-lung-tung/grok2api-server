"""
SSO -> CPA PKCE 转换器
用 curl_cffi 走完整 PKCE 流程，包括 OAuth consent 表单提交
"""
import json, os, sys, time, hashlib, base64, secrets, urllib.parse, argparse, re
import certifi, shutil
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    certifi.where().encode("ascii")
except Exception:
    _orig_cacert = certifi.where()
    _safe_ca_path = r"C:\Users\Public\cacert.pem"
    try:
        shutil.copy(_orig_cacert, _safe_ca_path)
        certifi.where = lambda: _safe_ca_path
    except Exception:
        pass

from curl_cffi import requests as cf_req, CurlOpt

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
REDIRECT_URI = "http://127.0.0.1:56121/callback"
TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
AUTHORIZE_URL = "https://auth.x.ai/oauth2/authorize"
SCOPE = "openid profile email offline_access grok-cli:access api:access"
def load_proxies():
    proxy_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proxies.txt")
    if os.path.exists(proxy_file):
        with open(proxy_file, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("=")]
            if lines:
                return lines
    return []

PROXY_LIST = load_proxies()

def get_proxy():
    _proxy_url = os.getenv("GROK_PROXY", "").strip()
    if _proxy_url:
        return {"http": _proxy_url, "https": _proxy_url}
    if os.getenv("USE_FREE_PROXIES", "false").lower() in ("1", "true", "yes"):
        if PROXY_LIST:
            p = secrets.choice(PROXY_LIST)
            if not any(p.startswith(prefix) for prefix in ["http://", "https://", "socks5://", "socks4://"]):
                p = "socks5://" + p
            return {"http": p, "https": p}
    return None

_env_proxy = os.getenv("GROK_PROXY", "").strip()
PROXY = _env_proxy if _env_proxy else None
KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")

_cpa_dir = os.getenv("CPA_AUTHS_DIR", "").strip()
if _cpa_dir and os.path.exists(_cpa_dir):
    AUTH_DIR = _cpa_dir
elif os.path.exists("D:/CLIProxyAPIPlus/auths"):
    AUTH_DIR = "D:/CLIProxyAPIPlus/auths"
else:
    AUTH_DIR = os.path.join(KEYS_DIR, "auths")
os.makedirs(AUTH_DIR, exist_ok=True)


def load_sso_tokens():
    grok_file = os.path.join(KEYS_DIR, "grok.txt")
    if not os.path.exists(grok_file):
        return []
    with open(grok_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_accounts():
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


def sso_to_cpa(sso_token, email=""):
    """用 SSO cookie 走 PKCE 流程，获取 CPA access_token。"""
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    sess = cf_req.Session()
    sess.proxies = get_proxy()
    sess.cookies.set("sso", sso_token, domain=".x.ai")

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

    print(f"  [{email}] 发起 PKCE 授权...")
    try:
        r = sess.get(auth_url, allow_redirects=False, timeout=30,
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    except Exception as e:
        print(f"  [{email}] 授权请求失败: {e}")
        return None

    code = None
    if r.status_code in (301, 302, 303, 307, 308):
        location = r.headers.get("Location", "")
        if location.startswith("/"):
            parsed_base = urllib.parse.urlparse(r.url)
            location = f"{parsed_base.scheme}://{parsed_base.netloc}{location}"
        if REDIRECT_URI in location or "code=" in location:
            parsed_loc = urllib.parse.urlparse(location)
            params_loc = urllib.parse.parse_qs(parsed_loc.query)
            code = params_loc.get("code", [None])[0]
        elif "/oauth2/consent" in location or "/consent" in location:
            # 需要 consent 页面 -> 用 requests 库提交（curl_cffi 的 cookie 在 POST 时不可靠）
            code = _handle_consent(sess, location, sso_token, code_verifier, email=email)

    if not code:
        print(f"  [{email}] [FAIL] 未获取到授权码")
        return None

    print(f"  [{email}] 获取到授权码: {code[:20]}...")
    print(f"  [{email}] 交换 token...")
    try:
        r = sess.post(TOKEN_ENDPOINT, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
            "client_id": CLIENT_ID,
        }, timeout=30)
    except Exception as e:
        print(f"  [{email}] Token 交换失败: {e}")
        return None

    if r.status_code != 200:
        print(f"  [{email}] [FAIL] Token 错误: {r.status_code} {r.text[:200]}")
        return None

    data = r.json()
    access_token = data.get("access_token")
    if not access_token:
        print(f"  [{email}] [FAIL] 响应中无 access_token: {json.dumps(data)[:200]}")
        return None

    print(f"  [{email}] [OK] CPA token 获取成功 (expires in {data.get('expires_in', '?')}s)")
    return {
        "access_token": access_token,
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 21600),
        "id_token": data.get("id_token", ""),
        "token_type": data.get("token_type", "Bearer"),
    }


def _handle_consent(sess, location, sso_token, code_verifier, email=""):
    """处理 OAuth consent 页面。用 DrissionPage 处理（自动过 CF + 点击 Allow）。"""
    from DrissionPage import ChromiumPage, ChromiumOptions

    _code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    _params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": _code_challenge,
        "code_challenge_method": "S256",
        "scope": SCOPE,
        "state": secrets.token_urlsafe(16),
    }
    _auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(_params)}"

    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome")
    co.set_user_data_path(temp_dir)
    page = ChromiumPage(co)

    try:
        print(f"  [{email}] [DrissionPage] 设置 SSO cookie...")
        page.get("https://accounts.x.ai/sign-up")
        time.sleep(2)
        page.set.cookies({"name": "sso", "value": sso_token, "domain": ".x.ai"})
        page.set.cookies({"name": "sso-rw", "value": sso_token, "domain": ".x.ai"})

        target_url = location if (location and ("consent" in location or "oauth2" in location)) else _auth_url
        print(f"  [{email}] [DrissionPage] 导航至 授权页...")
        page.get(target_url)
        time.sleep(3)

        code = None
        for attempt in range(15):
            curr_url = page.url
            if "code=" in curr_url or REDIRECT_URI in curr_url:
                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(curr_url).query)
                code = parsed.get("code", [None])[0]
                if code:
                    print(f"  [{email}] [DrissionPage] 成功从 URL 获取 Auth Code!")
                    break

            # 尝试点击 Allow / Authorize / 允许 按钮
            page.run_js('''
            var btns = document.querySelectorAll('button,[role=button]');
            for(var i=0; i<btns.length; i++){
                var t = (btns[i].innerText||'').toLowerCase();
                if(t.indexOf('allow')>=0 || t.indexOf('agree')>=0 || t.indexOf('authorize')>=0 || t.indexOf('允许')>=0 || t.indexOf('同意')>=0 || t.indexOf('continue')>=0){
                    btns[i].click(); break;
                }
            }
            ''')
            time.sleep(2)

        return code
    except Exception as e:
        print(f"  [{email}] [DrissionPage] Consent 异常: {e}")
def save_auth(email, cpa_data):
    """保存为代理可用的 xai-*.json 格式"""
    safe_email = email.replace("@", "_").replace(".", "_")
    path = os.path.join(AUTH_DIR, f"xai-{safe_email}.json")
    now = time.time()
    expires_in = cpa_data.get("expires_in", 21600)
    record = {
        "type": "xai", "auth_kind": "oauth",
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
        "disabled": False, "mint_method": "pkce", "protocol_flow": "pkce",
        "headers": {
            "X-XAI-Token-Auth": "xai-grok-cli",
            "x-grok-client-version": "0.2.93",
            "x-grok-client-identifier": "grok-shell",
        },
    }
    if cpa_data.get("id_token"):
        record["id_token"] = cpa_data["id_token"]
    os.makedirs(AUTH_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"  [{email}] 已保存至 {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="SSO -> CPA PKCE")
    parser.add_argument("--sso", help="单个 SSO token")
    parser.add_argument("--email", help="SSO 对应的邮箱")
    parser.add_argument("--all", action="store_true", help="转换所有未转换的 SSO")
    parser.add_argument("--dry-run", action="store_true", help="仅检查")
    args = parser.parse_args()
    if args.sso:
        email = args.email or "unknown"
        if args.dry_run:
            print(f"[DRY RUN] 将转换 SSO: {args.sso[:30]}... (email={email})")
            return
        result = sso_to_cpa(args.sso, email)
        if result: save_auth(email, result)
        else: print("转换失败"); sys.exit(1)
        return
    if args.all:
        accounts = load_accounts()
        if not accounts: print("accounts.txt 中无账号"); return
        existing = set()
        for fn in os.listdir(AUTH_DIR):
            if fn.startswith("xai-") and fn.endswith(".json"):
                try:
                    with open(os.path.join(AUTH_DIR, fn), encoding="utf-8") as f:
                        d = json.load(f)
                    if d.get("email"): existing.add(d["email"])
                except: pass
        pending = [a for a in accounts if a["email"] not in existing]
        print(f"总账号: {len(accounts)} 已转换: {len(existing)} 待转换: {len(pending)}")
        if args.dry_run:
            for a in pending: print(f"  [DRY RUN] {a['email']}")
            return
        success = 0
        for a in pending:
            print(f"\n转换: {a['email']}")
            result = sso_to_cpa(a["sso"], a["email"])
            if result:
                save_auth(a["email"], result)
                success += 1
            else: print(f"  {a['email']} 转换失败，跳过")
            time.sleep(3)
        print(f"\n完成: {success}/{len(pending)} 转换成功")
        return
    parser.print_help()


if __name__ == "__main__":
    main()