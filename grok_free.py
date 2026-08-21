"""
grok_free.py — Đăng ký tự động tài khoản Grok (Phiên bản miễn phí v4)
───────────────────────────────────────────────────────────────────────
- Email: Hỗ trợ đa nhà cung cấp (mailtm, tempmail, guerrilla, gmail, v.v.)
- Turnstile: DrissionPage trình duyệt + turnstile.render() tự động
- Mã OTP: gRPC-web gửi & xác minh
- Đăng ký: Next.js Server Action POST (curl_cffi)
- Xoay IP: Hỗ trợ Clash proxy rotation hoặc direct mode
- Đầu ra: SSO + email:password:sso → keys/
"""
import os, re, sys, json, time, random, string, struct, urllib.parse, argparse

# common.py tự động fix SSL certs + setup console UTF-8 khi import
import common  # noqa: F401

from dotenv import load_dotenv
load_dotenv()

from curl_cffi import requests as cf_req
from DrissionPage import ChromiumPage, ChromiumOptions
import requests  # requests chuẩn cho SSO redirect, tương thích auth.grokipedia.com

# ── Cấu hình ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://accounts.x.ai"
FALLBACK_SITE_KEY = "0x4AAAAAAAhr9JGVDZbrZOo0"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
def load_proxies():
    pfile = os.path.join(SCRIPT_DIR, "proxies.txt")
    if not os.path.exists(pfile):
        return []
    plist = []
    with open(pfile, encoding="utf-8", errors="ignore") as f:
        for line in f:
            l = line.strip()
            if l and not l.startswith("=") and ":" in l and "t.me" not in l:
                if not (l.startswith("http://") or l.startswith("https://") or l.startswith("socks5://")):
                    l = f"http://{l}"
                plist.append(l)
    return plist

PROXIES_LIST = load_proxies()
if PROXIES_LIST:
    print(f"[Proxy] ✅ 已自动从 proxies.txt 加载 {len(PROXIES_LIST)} 个 Proxy 节点")

GOOD_PROXIES_FILE = os.path.join(SCRIPT_DIR, "good_proxies.txt")

def load_good_proxies():
    if not os.path.exists(GOOD_PROXIES_FILE):
        return []
    glist = []
    with open(GOOD_PROXIES_FILE, encoding="utf-8", errors="ignore") as f:
        for line in f:
            l = line.strip()
            if l and ":" in l and not l.startswith("#"):
                if not (l.startswith("http://") or l.startswith("https://") or l.startswith("socks5://")):
                    l = f"http://{l}"
                glist.append(l)
    return glist

GOOD_PROXIES_LIST = load_good_proxies()
if GOOD_PROXIES_LIST:
    print(f"[Proxy VIP] ⭐ 已加载 {len(GOOD_PROXIES_LIST)} 个已验证的高可用 Proxy 优先复用")

def save_good_proxy(proxy_url):
    """Khi Proxy reg nick thành công, đưa lên ĐẦU FILE good_proxies.txt để ưu tiên tái sử dụng"""
    global GOOD_PROXIES_LIST
    if not proxy_url:
        return
    proxy_url = proxy_url.strip()
    if proxy_url in GOOD_PROXIES_LIST:
        GOOD_PROXIES_LIST.remove(proxy_url)
    GOOD_PROXIES_LIST.insert(0, proxy_url)
    try:
        lines = [l.strip() for l in open(GOOD_PROXIES_FILE, encoding="utf-8", errors="ignore") if l.strip()]
        new_lines = [proxy_url] + [l for l in lines if l != proxy_url]
        with open(GOOD_PROXIES_FILE, "w", encoding="utf-8") as f:
            for l in new_lines:
                f.write(l + "\n")
        print(f"  [Proxy VIP] ⭐ Đã đưa Proxy THÀNH CÔNG {proxy_url} lên ĐẦU DANH SÁCH ưu tiên!")
    except Exception:
        pass

_proxy_strikes = {}  # 记录每个 Proxy 失败次数，3 次才真正删除

def remove_bad_proxy(proxy_url):
    """Proxy 失败计数器：3 次失败才从列表中永久删除（避免误删临时抖动的好 Proxy）"""
    global PROXIES_LIST, GOOD_PROXIES_LIST, _proxy_strikes
    if not proxy_url:
        return
    raw_ip_port = proxy_url.replace("http://", "").replace("https://", "").replace("socks5://", "").replace("socks4://", "").strip()
    _proxy_strikes[raw_ip_port] = _proxy_strikes.get(raw_ip_port, 0) + 1
    strikes = _proxy_strikes[raw_ip_port]

    if strikes < 3:
        print(f"  [Proxy] ⚠️ {raw_ip_port} 失败 {strikes}/3 次，暂时保留")
        return

    # 3 次失败，永久删除
    if proxy_url in PROXIES_LIST:
        PROXIES_LIST.remove(proxy_url)
    if proxy_url in GOOD_PROXIES_LIST:
        GOOD_PROXIES_LIST.remove(proxy_url)
    for pfile in [os.path.join(SCRIPT_DIR, "proxies.txt"), GOOD_PROXIES_FILE]:
        if os.path.exists(pfile):
            try:
                lines = open(pfile, encoding="utf-8", errors="ignore").readlines()
                new_lines = [l for l in lines if raw_ip_port not in l]
                with open(pfile, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            except Exception:
                pass
    print(f"  [Proxy Prune] 🗑️ {raw_ip_port} 连续失败 3 次，已永久删除")

_last_used_proxy = None

def is_proxy_alive(px_url: str, timeout: float = 2.0) -> bool:
    """Kiểm tra tức thì (Pre-flight test) xem proxy có kết nối mượt tới xAI trong 2s không"""
    try:
        r = cf_req.get("https://accounts.x.ai", proxies={"http": px_url, "https": px_url},
                       timeout=timeout, impersonate="chrome120", verify=r"C:\Users\Admin\cacert.pem")
        return r.status_code in [200, 302, 307, 403]
    except Exception:
        return False

def get_best_proxy(direct=False):
    """Lấy và KIỂM TRA SỐNG TỨC THÌ (Pre-flight Check) Proxy từ good_proxies.txt trước khi cấp cho Chrome"""
    global _last_used_proxy
    if direct:
        return None
    pfile = GOOD_PROXIES_FILE
    if os.path.exists(pfile):
        lines = [l.strip() for l in open(pfile, encoding="utf-8", errors="ignore") if l.strip()]
        usable = [p for p in lines if not p.startswith("socks4://")]
        random.shuffle(usable)
        
        for p in usable:
            if p == _last_used_proxy and len(usable) > 1:
                continue
            # Kiểm tra sống tức thì trước khi cấp cho Chrome
            print(f"  [Proxy Check] 🔍 Đang kiểm tra độ sống tức thì: {p}...")
            if is_proxy_alive(p, timeout=2.5):
                _last_used_proxy = p
                tag = "🟣 SOCKS5" if p.startswith("socks5://") else "🟢 HTTP"
                print(f"  [Proxy VIP Active] {tag} ⭐ ĐÃ CHỌN PROXY SỐNG KHỎE 100%: {p}")
                return p
            else:
                print(f"  [Proxy Check] ❌ Proxy {p} đã chết/timeout, tự động loại bỏ...")
                remove_bad_proxy(p)

    plist = [x for x in PROXIES_LIST if not x.startswith("socks4://")]
    random.shuffle(plist)
    for p in plist[:10]:
        if is_proxy_alive(p, timeout=2.5):
            _last_used_proxy = p
            print(f"  [Proxy Active] 🟢 ĐÃ CHỌN PROXY SỐNG: {p}")
            return p

    return os.getenv("GROK_PROXY", "").strip() or None

_env_proxy = os.getenv("GROK_PROXY", "").strip()
PROXY = _env_proxy if _env_proxy else (random.choice(PROXIES_LIST) if PROXIES_LIST else None)
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "keys")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Clash 轮换器（可选，导入失败则跳过 IP 轮换）
try:
    from clash_rotator import (random_switch, switch_region, get_current_ip,
                                health as clash_health, snapshot, restore,
                                list_fast_nodes)
    HAS_CLASH = True
except ImportError:
    HAS_CLASH = False
    print("[!] clash_rotator 未找到，IP 轮换功能禁用")

# ═══════════════════════ 工具函数 ═══════════════════════

def rand_str(length=15):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def rand_name():
    n = random.randint(4, 6)
    return random.choice(string.ascii_uppercase) + ''.join(random.choice(string.ascii_lowercase) for _ in range(n - 1))

def _proxy_dict():
    if not PROXY:
        return None
    return {"http": PROXY, "https": PROXY}

# ── gRPC 编码（对齐原始 grok.py） ──

def encode_grpc_msg(field_id, val):
    key = (field_id << 3) | 2
    vb = val.encode("utf-8")
    payload = struct.pack("B", key) + struct.pack("B", len(vb)) + vb
    return b"\x00" + struct.pack(">I", len(payload)) + payload

def encode_grpc_verify(email, code):
    p1 = struct.pack("B", (1 << 3) | 2) + struct.pack("B", len(email)) + email.encode()
    p2 = struct.pack("B", (2 << 3) | 2) + struct.pack("B", len(code)) + code.encode()
    payload = p1 + p2
    return b"\x00" + struct.pack(">I", len(payload)) + payload

GRPC_HEADERS = {
    "content-type": "application/grpc-web+proto",
    "x-grpc-web": "1",
    "x-user-agent": "connect-es/2.1.1",
    "origin": SITE_URL,
    "referer": f"{SITE_URL}/sign-up?redirect=grok-com",
}

def send_email_code_grpc(session, email):
    """gRPC: 发送邮箱验证码"""
    url = f"{SITE_URL}/auth_mgmt.AuthManagement/CreateEmailValidationCode"
    data = encode_grpc_msg(1, email)
    try:
        res = session.post(url, data=data, headers=GRPC_HEADERS, timeout=20)
        grpc_status = str(res.headers.get("grpc-status", "0"))
        if res.status_code != 200 or grpc_status != "0":
            msg = urllib.parse.unquote(str(res.headers.get("grpc-message", "")))
            print(f"  [!] 发送验证码失败 (gRPC status={grpc_status}): {msg}")
            return False
        return True
    except Exception as e:
        print(f"  [!] 发送验证码异常: {e}")
        return False

def verify_email_code_grpc(session, email, code):
    """gRPC: 验证邮箱验证码"""
    url = f"{SITE_URL}/auth_mgmt.AuthManagement/VerifyEmailValidationCode"
    data = encode_grpc_verify(email, code)
    try:
        res = session.post(url, data=data, headers=GRPC_HEADERS, timeout=45)
        return res.status_code == 200
    except Exception as e:
        print(f"  [!] 验证验证码异常: {e}")
        return False


# ═══════════════════════ GPTMail 邮箱（新版 API） ═══════════════════════

class GPTMailInbox:
    """GPTMail 免费临时邮箱 —— 客户端生成邮箱 + inbox-token 注册

    API 流程（2026-07 新版）:
      1. GET  /api/domains/public  → 获取域名列表
      2. 客户端拼邮箱: prefix@random_domain
      3. POST /api/inbox-token     → 注册邮箱，获取 JWT token
      4. GET  /api/emails?email=.. → 轮询邮件
      5. GET  /api/email/{id}      → 获取邮件正文
    """

    def __init__(self):
        proxy_dict = _proxy_dict() if PROXY else None
        self.sess = cf_req.Session(impersonate="chrome120")
        if proxy_dict:
            self.sess.proxies = proxy_dict
        self.email = ""
        self.token = ""
        self._domains = []

    def _get_domains(self):
        """获取活跃域名列表"""
        if self._domains:
            return self._domains
        try:
            # 预热
            self.sess.get("https://mail.chatgpt.org.uk/", timeout=15)
        except Exception:
            pass
        r = self.sess.get("https://mail.chatgpt.org.uk/api/domains/public", timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"获取域名失败: {r.status_code}")
        data = r.json()
        domains_list = (data.get("data") or {}).get("domains") or []
        self._domains = [d["domain_name"] for d in domains_list if d.get("is_active")]
        if not self._domains:
            raise RuntimeError("无活跃域名")
        return self._domains

    def create(self):
        """生成邮箱并注册"""
        domains = self._get_domains()
        prefix = rand_str(10)
        domain = random.choice(domains)
        self.email = f"{prefix}@{domain}"

        # 注册邮箱到 inbox token
        r = self.sess.post(
            "https://mail.chatgpt.org.uk/api/inbox-token",
            headers={"Content-Type": "application/json"},
            json={"email": self.email},
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(f"inbox-token 失败: {r.status_code}")
        data = r.json()
        if not data.get("success"):
            raise RuntimeError(f"inbox-token 返回失败: {data}")
        self.token = (data.get("auth") or {}).get("token") or ""
        if not self.token:
            raise RuntimeError("未获取到 inbox token")
        return self.email

    def wait_code(self, timeout=60, interval=5):
        """轮询 GPTMail 获取验证码"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(interval)
            try:
                r = self.sess.get(
                    f"https://mail.chatgpt.org.uk/api/emails?email={urllib.parse.quote(self.email)}",
                    headers={"x-inbox-token": self.token},
                    timeout=15,
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                emails = (data.get("data") or {}).get("emails") or data.get("data") or []
                if isinstance(emails, dict):
                    emails = [emails]
                for msg in (emails if isinstance(emails, list) else []):
                    subject = str(msg.get("subject") or "")
                    body = str(msg.get("text") or msg.get("html") or msg.get("body") or "")
                    text = subject + " " + body
                    m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", text)
                    if m:
                        return m.group(1) + m.group(2)

                # 如果邮件列表有 ID，获取详情
                for msg in (emails if isinstance(emails, list) else []):
                    msg_id = msg.get("id") or msg.get("message_id")
                    if msg_id:
                        r2 = self.sess.get(
                            f"https://mail.chatgpt.org.uk/api/email/{urllib.parse.quote(str(msg_id))}",
                            headers={"x-inbox-token": self.token},
                            timeout=15,
                        )
                        if r2.status_code == 200:
                            detail = r2.json()
                            d = (detail.get("data") or detail)
                            text2 = str(d.get("subject") or "") + " " + str(d.get("text") or d.get("html") or d.get("body") or "")
                            m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", text2)
                            if m:
                                return m.group(1) + m.group(2)
            except Exception:
                continue
        return None


# ═══════════════════════ 浏览器初始化 ═══════════════════════

def browser_init(headless=True, direct=False):
    """打开注册页 → 获取 Action ID + Site Key + Turnstile Token + State Tree"""

    co = ChromiumOptions()
    co.auto_port()
    if headless:
        co.set_argument("--window-position=-32000,-32000")
    # 强制将 Chrome 缓存及 Profile 存储在 D 盘 workspace 中，每个 Session 独立目录避免状态冲突
    chrome_temp = os.path.join(SCRIPT_DIR, "temp_chrome", f"prof_{random.randint(10000, 99999)}")
    os.makedirs(chrome_temp, exist_ok=True)
    co.set_argument(f"--user-data-dir={chrome_temp}")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--incognito")
    # 随机窗口大小减少指纹一致性
    w = random.randint(1200, 1400)
    h = random.randint(800, 1000)
    co.set_argument(f"--window-size={w},{h}")
    cur_proxy = get_best_proxy(direct=direct)
    if cur_proxy:
        # Chrome --proxy-server cần giữ nguyên socks5:// hoặc socks4://, chỉ bỏ http://
        if cur_proxy.startswith("socks5://") or cur_proxy.startswith("socks4://"):
            proxy_addr = cur_proxy  # giữ nguyên socks5://ip:port
        else:
            proxy_addr = cur_proxy.replace("http://", "").replace("https://", "")
        co.set_argument(f"--proxy-server={proxy_addr}")
        print(f"  [Proxy] 🔒 100% Proxy Mode: {proxy_addr}")
    else:
        print(f"  [Network] 🌐 Direct Mode: Sử dụng mạng trực tiếp (Không qua proxy)")
    try:
        co.set_timeouts(12)
        page = ChromiumPage(co)
        print("[Browser] 🌐 Đang mở trang đăng ký Grok...")
        page.get(f"{SITE_URL}/sign-up?redirect=grok-com", timeout=12)
        time.sleep(3)

        html = page.html
        if not html or len(html) < 200:
            if cur_proxy:
                remove_bad_proxy(cur_proxy)
            raise RuntimeError("Tải trang thất bại (Proxy có thể đã mất kết nối)")
    except Exception as e:
        if cur_proxy:
            remove_bad_proxy(cur_proxy)
        try:
            page.quit()
        except Exception:
            pass
        raise e

    # --- Site Key ---
    site_key = FALLBACK_SITE_KEY
    m = re.search(r'sitekey":"(0x4[a-zA-Z0-9_-]+)"', html)
    if m:
        site_key = m.group(1)
    print(f"[Browser] 🔑 SiteKey: {site_key}")

    # --- Action ID ---
    js_urls = re.findall(r"/_next/static/chunks/[^\"'\s>]+\.js", html)
    action_id = None
    js_sess = cf_req.Session(impersonate="chrome120")
    if cur_proxy:
        js_sess.proxies = {"http": cur_proxy, "https": cur_proxy}
    for js_path in js_urls:
        url = js_path if js_path.startswith("http") else f"{SITE_URL}{js_path}"
        try:
            js = js_sess.get(url, timeout=15).text
            # 支持新旧两种格式: release:"hex40" 或旧版 7f+hex40
            m = re.search(r'release[:\s]*["\']([a-fA-F0-9]{40})["\']', js)
            if not m:
                m = re.search(r'7f[a-fA-F0-9]{40}', js)
            if m:
                action_id = m.group(1) if m.lastindex else m.group(0)
                print(f"[Browser] 🆔 ActionID: {action_id}")
                break
        except Exception:
            continue
    if not action_id:
        try:
            cache_file = os.path.join(SCRIPT_DIR, ".action_id.cache")
            if os.path.exists(cache_file):
                cached = open(cache_file, encoding="utf-8").read().strip()
                if re.match(r"^(7f)?[a-fA-F0-9]{40}$", cached):
                    action_id = cached
                    print(f"[Browser] 💾 Sử dụng Action ID từ cache: {action_id}")
        except Exception:
            pass
    if not action_id:
        raise RuntimeError("Không tìm thấy Action ID, không thể đăng ký")

    # --- State Tree ---
    state_tree = ""
    m = re.search(r'next-router-state-tree":"([^"]+)"', html)
    if m:
        state_tree = m.group(1)

    # --- Click chọn email ---
    print("[Browser] 🖱️ Đang click chọn đăng ký bằng Email...")
    page.run_js('''
    var all=document.querySelectorAll('button,[role=button]');
    for(var i=0;i<all.length;i++){
        if(!all[i].offsetParent) continue;
        var t=(all[i].innerText||'').trim();
        if(t.indexOf('邮箱')>=0||t.indexOf('email')>=0||t.indexOf('Email')>=0){
            all[i].click(); break;
        }
    }
    ''')
    time.sleep(3)

    # --- Turnstile ---
    print("[Browser] 🛡️ Đang chờ giải mã Cloudflare Turnstile...")
    ts_token = ""
    for attempt in range(4):
        time.sleep(2)
        ts_token = page.run_js(
            'return document.querySelector("[name=cf-turnstile-response]")?.value||""')
        if len(ts_token) > 50:
            print(f"[Browser] ⚡ Turnstile tự động vượt qua (Lần thử {attempt+1})")
            break
        if attempt in (2, 5, 10):
            try:
                iframe = page.ele("@src*turnstile", timeout=1) or page.ele("@src*challenges", timeout=1)
                if iframe:
                    iframe.click()
            except Exception:
                pass

    if len(ts_token) < 50:
        print("[Browser] ⏳ Chờ tự động quá lâu, tiến hành kích hoạt thủ công (timeout 70s)...")
        ts_token = page.run_js('''
        var _sitekey = arguments[0];
        return new Promise(function(resolve, _reject) {
            var sitekey = _sitekey;
            var tsDiv = document.createElement('div');
            tsDiv.id = '_grok_free_ts';
            tsDiv.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999';
            document.body.appendChild(tsDiv);

            var timeout = setTimeout(function() { resolve('timeout'); }, 60000);

            try {
                turnstile.render('#'+tsDiv.id, {
                    sitekey: sitekey, theme: 'light',
                    callback: function(token) {
                        clearTimeout(timeout);
                        var hidden = document.querySelector('[name="cf-turnstile-response"]');
                        if (hidden) hidden.value = token;
                        resolve(token);
                    },
                    'error-callback': function(e) {
                        clearTimeout(timeout);
                        resolve('error:' + (e && e.message ? e.message : String(e)));
                    }
                });
            } catch(e) {
                clearTimeout(timeout);
                resolve('exception:' + (e && e.message ? e.message : String(e)));
            }
        });
        ''', site_key, timeout=75)
        print(f"[Browser] 🔄 Kết quả kích hoạt Turnstile: {ts_token[:80] if ts_token else 'None'}...")

    if not ts_token or ts_token.startswith('timeout') or ts_token.startswith('error'):
        ts_token = page.run_js(
            'return document.querySelector("[name=cf-turnstile-response]")?.value||""')
        if len(ts_token) < 50:
            page.quit()
            raise RuntimeError(f"Turnstile chưa giải quyết được: {ts_token}")

    print(f"[Browser] ✅ Cloudflare Turnstile đã giải quyết thành công! ({len(ts_token)} chars)")

    return {
        "site_key": site_key,
        "action_id": action_id,
        "state_tree": state_tree,
        "ts_token": ts_token,
        "page": page,
        "cur_proxy": cur_proxy,
    }


# ═══════════════════════ 注册流程 ═══════════════════════

def solve_turnstile(page, site_key):
    """在浏览器中解决 Turnstile，返回新 token。每次注册前调用"""
    # 刷新注册页
    page.get(f"{SITE_URL}/sign-up?redirect=grok-com")
    time.sleep(3)

    # 点击邮箱选项
    page.run_js('''
    var all=document.querySelectorAll('button,[role=button]');
    for(var i=0;i<all.length;i++){
        if(!all[i].offsetParent) continue;
        var t=(all[i].innerText||'').trim();
        if(t.indexOf('邮箱')>=0||t.indexOf('email')>=0||t.indexOf('Email')>=0){
            all[i].click(); break;
        }
    }
    ''')
    time.sleep(2)

    # 等待自然 Turnstile 解决
    ts_token = ""
    for attempt in range(35):
        ts_token = page.run_js(
            'return document.querySelector("[name=cf-turnstile-response]")?.value||""')
        if len(ts_token) > 50:
            break

    # fallback: 手动渲染
    if len(ts_token) < 50:
        ts_token = page.run_js('''
        var _sitekey = arguments[0];
        return new Promise(function(resolve, _reject) {
            var sitekey = _sitekey;
            var tsDiv = document.createElement('div');
            tsDiv.id = '_grok_fresh_ts';
            tsDiv.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999';
            document.body.appendChild(tsDiv);
            var timeout = setTimeout(function() { resolve('timeout'); }, 60000);
            try {
                turnstile.render('#'+tsDiv.id, {
                    sitekey: sitekey, theme: 'light',
                    callback: function(token) {
                        clearTimeout(timeout);
                        var hidden = document.querySelector('[name="cf-turnstile-response"]');
                        if (hidden) hidden.value = token;
                        resolve(token);
                    },
                    'error-callback': function(e) {
                        clearTimeout(timeout);
                        resolve('error:' + (e && e.message ? e.message : String(e)));
                    }
                });
            } catch(e) {
                clearTimeout(timeout);
                resolve('exception:' + (e && e.message ? e.message : String(e)));
            }
        });
        ''', site_key, timeout=75)

    if not ts_token or ts_token.startswith('timeout') or ts_token.startswith('error'):
        return None
    return ts_token


def register_one(cfg):
    """Đăng ký 1 tài khoản Grok → Trả về (email, password, sso) hoặc None"""
    provider = cfg.get("email_provider", "mailtm")
    cur_proxy = cfg.get("cur_proxy")
    # ── Tạo email ──
    print(f"[Mail] 📧 Đang tạo hộp thư {provider}...")
    try:
        from email_service import EmailService
        email_svc = EmailService(provider=provider, proxies={"http": cur_proxy, "https": cur_proxy} if cur_proxy else None)
        token_like, email = email_svc.create_email()
        if not email:
            print(f"[Mail] ❌ Dịch vụ {provider} trả về None")
            if cur_proxy:
                remove_bad_proxy(cur_proxy)
            return None
    except Exception as e:
        print(f"[Mail] ❌ Dịch vụ {provider} lỗi: {e}")
        return None
    print(f"[Mail] 📬 Email: {email}")

    # ── curl_cffi session ──
    sess = cf_req.Session(impersonate="chrome120")
    if cur_proxy:
        sess.proxies = {"http": cur_proxy, "https": cur_proxy}
    try:
        sess.get(SITE_URL, timeout=10)
    except Exception:
        pass

    # ── Step 1: Gửi mã xác nhận OTP (gRPC) ──
    print(f"[{email}] 📤 Đang gửi mã OTP xác nhận (gRPC)...")
    if not send_email_code_grpc(sess, email):
        print(f"[{email}] ❌ Gửi mã OTP thất bại")
        if cur_proxy:
            remove_bad_proxy(cur_proxy)
        return None
    print(f"[{email}] ✅ Mã OTP đã được gửi")

    # ── Step 2: Đợi email nhận mã OTP ──
    print(f"[{email}] ⏳ Đang đợi email chứa mã OTP...")
    code = None
    for _ in range(36):  # 36 x 5s = 180s
        time.sleep(5)
        content = email_svc.fetch_first_email(token_like)
        if content:
            m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", content)
            if m:
                code = m.group(1) + m.group(2)
                break
    if not code:
        print(f"[{email}] ⚠️ Không nhận được mã OTP (Quá thời gian chờ)")
        return None
    print(f"[{email}] 🔑 Đã nhận mã OTP: {code}")

    # ── Step 3: Xác thực mã OTP (gRPC) ──
    print(f"[{email}] 🔍 Đang xác thực mã OTP (gRPC)...")
    if not verify_email_code_grpc(sess, email, code):
        print(f"[{email}] ❌ Mã OTP không hợp lệ")
        return None
    print(f"[{email}] ✅ Mã OTP chính xác")

    # ── Step 4: Turnstile token ──
    ts_token = cfg.get("ts_token")
    if not ts_token:
        print(f"[{email}] ❌ Thiếu Turnstile token")
        return None
    print(f"[{email}] ✅ Turnstile token đã sẵn sàng ({len(ts_token)} chars)")

    # ── Step 5: Chuẩn bị thông tin tài khoản ──
    password = rand_str(14) + "Aa1!"
    first = rand_name()
    last = rand_name()

    # ── Step 6: Gửi dữ liệu đăng ký POST ──
    print(f"[{email}] 🚀 Đang gửi dữ liệu tạo tài khoản...")
    try:
        sess.get(SITE_URL, timeout=10)
    except Exception:
        pass

    cf_bm = sess.cookies.get("__cf_bm", "")
    headers = {
        "user-agent": UA,
        "accept": "text/x-component",
        "content-type": "text/plain;charset=UTF-8",
        "origin": SITE_URL,
        "referer": f"{SITE_URL}/sign-up",
        "cookie": f"__cf_bm={cf_bm}",
        "next-router-state-tree": cfg["state_tree"],
        "next-action": cfg["action_id"],
    }

    payload = [{
        "emailValidationCode": code,
        "createUserAndSessionRequest": {
            "email": email,
            "givenName": first,
            "familyName": last,
            "clearTextPassword": password,
            "tosAcceptedVersion": "$undefined",
        },
        "turnstileToken": ts_token,
        "promptOnDuplicateEmail": True,
    }]

    try:
        r = sess.post(f"{SITE_URL}/sign-up", json=payload, headers=headers, timeout=30)
        print(f"[{email}] Trạng thái POST: {r.status_code}")
    except Exception as e:
        print(f"[{email}] ❌ Lỗi gửi POST: {e}")
        return None

    if r.status_code != 200:
        print(f"[{email}] ❌ Đăng ký thất bại: {r.text[:300]}")
        return None

    # ── Step 7: Trích xuất SSO Token ──
    resp_text = r.text
    sso = None
    
    # Cách 1: Từ Header redirect
    for hdr_name in ("x-middleware-rewrite", "x-action-redirect", "location"):
        hdr_val = r.headers.get(hdr_name, "")
        if "set-cookie?q=" in hdr_val:
            try:
                import base64
                q_val = hdr_val.split("set-cookie?q=")[1].split("&")[0]
                decoded = base64.b64decode(urllib.parse.unquote(q_val)).decode("utf-8")
                j_obj = json.loads(decoded)
                sess_cookie = j_obj.get("sessionCookie", "")
                if "sso=" in sess_cookie:
                    sso = sess_cookie.split("sso=")[1].split(";")[0]
                    print(f"[{email}] 🎉 Trích xuất thành công SSO Token từ {hdr_name} Header!")
                    break
            except Exception as e:
                pass

    # Cách 2: Từ Session Cookie
    if not sso:
        for c_name in ("sso", "sso-rw", "auth_token"):
            if sess.cookies.get(c_name):
                sso = sess.cookies.get(c_name)
                print(f"[{email}] 🎉 Trích xuất thành công SSO Token từ Session Cookie ({c_name})!")
                break

    # Cách 3: Tìm set-cookie URL trong response body
    if not sso:
        sso_url = None
        for pat in [
            r'(https://[^"\s]+set-cookie\?q=[^:"\s]+)1:',
            r'(https://[^"\s]+set-cookie\?q=[^"\s]+)',
            r'https://[^"\s]*set-cookie[^"\s]*',
        ]:
            m = re.search(pat, resp_text)
            if m:
                sso_url = m.group(0).rstrip("1:").rstrip("2:").rstrip("3:")
                break

        if sso_url:
            print(f"[{email}] 🔗 SSO URL: {sso_url[:100]}...")
            try:
                rs = requests.Session()
                if PROXY:
                    rs.proxies = {"http": PROXY, "https": PROXY}
                res_sso = rs.get(sso_url, allow_redirects=True, timeout=15, headers={"User-Agent": UA})
                for c in rs.cookies:
                    if c.name in ("sso", "sso-rw", "auth_token") and c.value:
                        sso = c.value
                        break
            except Exception as e:
                try:
                    sess.get(sso_url, allow_redirects=True, timeout=15)
                    for c_name in ("sso", "sso-rw", "auth_token"):
                        if sess.cookies.get(c_name):
                            sso = sess.cookies.get(c_name)
                            break
                except Exception:
                    pass

            if not sso and "q=" in sso_url:
                try:
                    import base64
                    parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(sso_url).query).get("q", [])
                    if parsed_q and parsed_q[0]:
                        q_str = parsed_q[0]
                        try:
                            decoded = base64.b64decode(urllib.parse.unquote(q_str)).decode("utf-8")
                            j_obj = json.loads(decoded)
                            sess_cookie = j_obj.get("sessionCookie", "")
                            if "sso=" in sess_cookie:
                                sso = sess_cookie.split("sso=")[1].split(";")[0]
                        except Exception:
                            sso = q_str
                        if sso:
                            print(f"[{email}] 🎉 Trích xuất thành công SSO Token từ tham số URL q!")
                except Exception:
                    pass

    if sso:
        print(f"[{email}] ✅ ĐĂNG KÝ THÀNH CÔNG! SSO Token: {sso[:30]}...")
        if cur_proxy:
            save_good_proxy(cur_proxy)
        with open(os.path.join(OUTPUT_DIR, "grok.txt"), "a", encoding="utf-8") as f:
            f.write(sso + "\n")
        with open(os.path.join(OUTPUT_DIR, "accounts.txt"), "a", encoding="utf-8") as f:
            f.write(f"{email}:{password}:{sso}\n")
        return (email, password, sso)
    else:
        print(f"[{email}] ⚠️ Không tìm thấy SSO Token trong phản hồi, 300 ký tự đầu:")
        print(f"  {resp_text[:300]}")

    return None


# ═══════════════════════ 主程序 ═══════════════════════

def main():
    parser = argparse.ArgumentParser(description="Grok 全自动注册")
    parser.add_argument("--count", type=int, default=3, help="注册数量（默认 3）")
    parser.add_argument("--no-rotate", action="store_true", help="禁用 IP 轮换")
    parser.add_argument("--rotate-interval", type=int, default=1, help="每注册 N 个后切换 IP（默认 1，即每次切换）")
    parser.add_argument("--min-delay", type=int, default=8, help="注册间隔最小值（秒，默认 8）")
    parser.add_argument("--max-delay", type=int, default=25, help="注册间隔最大值（秒，默认 25）")
    parser.add_argument("--rotate-region", action="store_true", help="切换不同区域节点（而非随机节点）")
    parser.add_argument("--email-provider", choices=["mailtm", "mailgw", "tempmail", "guerrilla", "gptmail", "luckmail", "gmail", "tmail", "fce", "outlook", "sfrankie"], default=os.getenv("EMAIL_PROVIDER", "mailtm"), help="Nhà cung cấp email ảo")
    parser.add_argument("--headless", action="store_true", default=False, help="无头模式（默认 False）")
    parser.add_argument("--no-headless", dest="headless", action="store_false", help="显示窗口模式")
    parser.add_argument("--direct", "--no-proxy", dest="direct", action="store_true", default=False, help="Sử dụng mạng trực tiếp (Direct Connection), không qua proxy")
    args = parser.parse_args()

    print("=" * 55)
    print(f"Grok 注册 · 免费版 v4 (Provider={args.email_provider} + DrissionPage + gRPC)")
    print(f"数量: {args.count}  IP轮换: {'✅' if not args.no_rotate and HAS_CLASH else '❌'}  Direct: {'✅' if args.direct else '❌'}")
    print("=" * 55)

    # ── Clash: 快照当前节点（注册完恢复） ──
    original_node = None
    if not args.no_rotate and HAS_CLASH:
        try:
            original_node = snapshot()
            h = clash_health()
            # 显示低延迟节点数
            fast, slow = list_fast_nodes()
            print(f"[Clash] 快照: {h['current_node'][:40]}")
            print(f"[Clash] 出口 IP: {h['current_ip']}  ({h['region']})")
            print(f"[Clash] 低延迟节点: {len(fast)}  慢/断线: {len(slow)}")
            if slow:
                for n, reason in slow[:3]:
                    print(f"[Clash]   ⚠ {n[:35]} — {reason}")
        except Exception as e:
            print(f"[Clash] ⚠️ 检查失败: {e}")

    # 2. 注册循环
    success = 0
    fail = 0
    t0 = time.time()
    used_regions = set()

    for i in range(args.count):
        print(f"\n{'─'*40}")
        print(f"第 {i+1}/{args.count} 次注册")
        print(f"{'─'*40}")

        # ── IP 轮换 ──
        if not args.no_rotate and HAS_CLASH and i > 0 and i % args.rotate_interval == 0:
            try:
                if args.rotate_region:
                    switch_region(exclude_regions=used_regions)
                else:
                    random_switch()
                new_ip = get_current_ip()
                if new_ip:
                    print(f"  [IP] 新出口 IP: {new_ip}")
            except Exception as e:
                print(f"  [IP] ⚠️ 切换失败: {e}，继续使用当前 IP")

        cfg = None
        try:
            cfg = browser_init(headless=args.headless, direct=args.direct)
            if cfg:
                cfg["email_provider"] = args.email_provider
                result = register_one(cfg)
                if result:
                    success += 1
                    avg = (time.time() - t0) / success
                    print(f"  ✅ 成功={success} 失败={fail} 均速={avg:.0f}s/个")
                else:
                    fail += 1
                    print(f"  ❌ 失败 成功={success} 失败={fail}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            fail += 1
            print(f"[!] 异常: {e}")
        finally:
            if cfg and cfg.get("page"):
                try:
                    cfg["page"].quit()
                except Exception:
                    pass
            if os.name == "nt":
                os.system("taskkill /F /IM chrome.exe /T >nul 2>&1")

        # ── 随机间隔（最后一个不需要等待） ──
        if i < args.count - 1:
            delay = random.uniform(args.min_delay, args.max_delay)
            print(f"  ⏳ 等待 {delay:.1f}s...")
            time.sleep(delay)

    # ── 恢复原始节点 ──
    if original_node and HAS_CLASH:
        try:
            restore(original_node)
        except Exception as e:
            print(f"[Clash] ⚠️ 恢复节点失败: {e}")

    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"结束。成功={success} 失败={fail} 耗时={elapsed:.0f}s")
    if success > 0:
        print(f"SSO 已保存至: {OUTPUT_DIR}")
    print(f"{'='*55}")

    # 🧹 自动清理所有 Chrome 残留进程（防止 Taskbar 堆积图标）
    if sys.platform == "win32":
        try:
            subprocess.run("taskkill /F /IM chrome.exe /T", shell=True,
                           capture_output=True, timeout=10)
        except Exception:
            pass


if __name__ == "__main__":
    main()
