"""
SSO → OAuth Device Flow 铸造模块 (2026-08-06)
替换被 CF 拦截的 PKCE 方案 (sso_to_cpa.py)。

原理: x.ai OAuth Device Authorization Grant
- 关键: scope 必须为 7 个, 不能加 conversations/workspaces (该 client 未授权, 加了 Access denied)
- 授权: 有头 Chrome 注入 SSO cookie → 打开授权页自动点"继续/允许" → 轮询 token

接口: sso_to_device(sso, email) -> cpa_data (与 sso_to_cpa.py 返回结构一致)
"""
import json, sys, time, base64, asyncio, urllib.request, urllib.error, urllib.parse, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
SCOPE = "openid profile email offline_access grok-cli:access api:access"
_env_proxy = os.getenv("GROK_PROXY", "").strip()
PROXY = _env_proxy if _env_proxy else None


def save_auth(email, cpa_data):
    from sso_to_cpa import save_auth as _sa
    return _sa(email, cpa_data)


def _http_json(url, method="GET", form=None, timeout=40):
    handlers = []
    if PROXY:
        handlers.append(urllib.request.ProxyHandler({"https": PROXY, "http": PROXY}))
    opener = urllib.request.build_opener(*handlers)
    data = urllib.parse.urlencode(form).encode() if form else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "grok-register-cpa/1.0")
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read().decode(errors="replace")
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def _browser_authorize_drission(vuc, sso_jwt, email=""):
    """DrissionPage 浏览器 + 注入 SSO cookie, 自动点授权按钮"""
    from DrissionPage import ChromiumPage, ChromiumOptions
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.set_argument('--window-position=-32000,-32000')
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_chrome")
    co.set_user_data_path(temp_dir)
    page = ChromiumPage(co)
    try:
        print(f"  [{email}] [DrissionPage] 注入 SSO cookie...")
        page.get("https://accounts.x.ai/sign-in")
        time.sleep(2)
        page.set.cookies({"name": "sso", "value": sso_jwt, "domain": ".x.ai", "path": "/"})
        page.set.cookies({"name": "sso-rw", "value": sso_jwt, "domain": ".x.ai", "path": "/"})
        page.set.cookies({"name": "sso", "value": sso_jwt, "domain": "accounts.x.ai", "path": "/"})
        page.set.cookies({"name": "sso-rw", "value": sso_jwt, "domain": "accounts.x.ai", "path": "/"})

        print(f"  [{email}] [DrissionPage] 导航至 Device 授权 URL...")
        page.get(vuc)
        time.sleep(3)

        for attempt in range(15):
            curr_url = page.url
            if "/device/done" in curr_url or "success" in curr_url or "approved" in curr_url:
                print(f"  [{email}] [DrissionPage] ✅ 授权成功!")
                return True
            page.run_js('''
            var btns = document.querySelectorAll('button,[role=button]');
            for(var i=0; i<btns.length; i++){
                var t = (btns[i].innerText||'').toLowerCase();
                if(t.indexOf('continue')>=0 || t.indexOf('allow')>=0 || t.indexOf('agree')>=0 || t.indexOf('authorize')>=0 || t.indexOf('继续')>=0 || t.indexOf('允许')>=0 || t.indexOf('同意')>=0){
                    btns[i].click(); break;
                }
            }
            ''')
            time.sleep(2)
        return False
    except Exception as e:
        print(f"  [{email}] Authorize 异常: {e}")
        return False
    finally:
        try:
            page.quit()
        except Exception:
            pass


def sso_to_device(sso_token, email=""):
    """Device Flow 铸造: SSO cookie → OAuth AT/RT。
    返回 dict(access_token/refresh_token/expires_in/token_type) 或 None"""
    try:
        s, p = _http_json("https://auth.x.ai/oauth2/device/code", "POST",
                          {"client_id": CLIENT_ID, "scope": SCOPE})
        if s != 200 or not isinstance(p, dict) or "device_code" not in p:
            print(f"  [DEVICE] device/code 失败 HTTP {s}: {str(p)[:150]}")
            return None
        dc = p["device_code"]
        vuc = p.get("verification_uri_complete")
        ok = _browser_authorize_drission(vuc, sso_token, email=email)
        if not ok:
            print("  [DEVICE] 授权未确认, 继续轮询")
        deadline = time.time() + 60
        interval = max(int(p.get("interval", 5)), 1)
        while time.time() < deadline:
            time.sleep(interval)
            s, t = _http_json("https://auth.x.ai/oauth2/token", "POST", {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": dc, "client_id": CLIENT_ID})
            if s == 200 and isinstance(t, dict) and t.get("access_token"):
                return {
                    "access_token": t["access_token"],
                    "refresh_token": t.get("refresh_token", ""),
                    "expires_in": int(t.get("expires_in") or 21600),
                    "token_type": t.get("token_type", "Bearer"),
                }
            err = t.get("error") if isinstance(t, dict) else None
            if err in ("access_denied", "expired_token"):
                print(f"  [DEVICE] token 失败: {err}: {t.get('error_description', '')[:80]}")
                return None
            if err == "slow_down":
                interval += 5
        print("  [DEVICE] 轮询超时")
        return None
    except Exception as e:
        print(f"  [DEVICE] 异常: {str(e)[:120]}")
        return None


if __name__ == "__main__":
    # 单测: 从 accounts.txt 取一个未使用账号测试
    sso_map = {}
    for l in open(os.path.join(os.path.dirname(__file__), "keys/accounts.txt"),
                  encoding="utf-8-sig").read().splitlines():
        parts = l.split(":")
        if len(parts) >= 3:
            sso_map[parts[0]] = ":".join(parts[2:])
    email = sys.argv[1] if len(sys.argv) > 1 else list(sso_map.keys())[0]
    print(f"测试铸造: {email}")
    result = sso_to_device(sso_map.get(email, ""), email)
    if result:
        print(f"✅ 成功: AT={result['access_token'][:30]}... RT={result['refresh_token'][:20]}...")
    else:
        print("❌ 失败")
