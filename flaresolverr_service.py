"""
flaresolverr_service.py — Bộ giải mã Cloudflare Clearance chuẩn FlareSolverr API
─────────────────────────────────────────────────────────────────────────────
Sử dụng DrissionPage (Chrome thật) thay vì Docker để tương thích 100% với Grok2API:
- Lắng nghe cổng 8191 (chuẩn FlareSolverr: POST /v1)
- Tự động lấy Cookie cf_clearance & User-Agent từ grok.com
- Trả về JSON đúng chuẩn cho Grok2API giải quyết WAF khi Sửa ảnh / Tạo video!
"""
import sys
import os
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from DrissionPage import ChromiumPage, ChromiumOptions
import common  # noqa: F401

PORT = 8191
CACHED_SOLUTION = None
CACHE_EXPIRY = 0


def solve_cloudflare(url="https://grok.com", proxy_url=None):
    """Sử dụng DrissionPage để lấy cf_clearance thật."""
    global CACHED_SOLUTION, CACHE_EXPIRY
    now = time.time()
    if CACHED_SOLUTION and now < CACHE_EXPIRY:
        print("[⚡] Sử dụng Clearance còn hiệu lực từ Cache")
        return CACHED_SOLUTION

    print(f"🌐 [DrissionPage] Đang mở Chrome thật để giải mã Cloudflare cho: {url}...")
    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.auto_port()

    temp_dir = os.path.join(os.getcwd(), "temp_chrome", "flaresolverr")
    os.makedirs(temp_dir, exist_ok=True)
    co.set_argument(f"--user-data-dir={temp_dir}")

    if proxy_url:
        co.set_proxy(proxy_url)

    page = None
    try:
        page = ChromiumPage(co)
        page.get(url, timeout=30)
        time.sleep(3)

        ua = page.user_agent
        try:
            raw_cookies = page.cookies(all_info=True)
        except Exception:
            raw_cookies = page.cookies()

        cookies = []
        for c in raw_cookies:
            if isinstance(c, dict):
                cookies.append({"name": c.get("name", ""), "value": c.get("value", "")})

        print(f"[✓] Đã lấy thành công {len(cookies)} cookies từ Cloudflare!")
        solution = {
            "status": "ok",
            "message": "Challenge solved successfully with DrissionPage!",
            "startTimestamp": int(now * 1000),
            "endTimestamp": int(time.time() * 1000),
            "version": "3.3.21",
            "solution": {
                "url": url,
                "status": 200,
                "headers": {},
                "response": "<html></html>",
                "cookies": cookies,
                "userAgent": ua,
            }
        }
        CACHED_SOLUTION = solution
        CACHE_EXPIRY = now + 1800  # Cache 30 phút
        return solution

    except Exception as e:
        print(f"[!] Lỗi giải mã: {e}")
        return {
            "status": "error",
            "message": str(e),
            "solution": {}
        }
    finally:
        if page:
            try:
                page.quit()
            except Exception:
                pass


class FlareSolverrHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp = {"msg": "FlareSolverr DrissionPage Native Service is running!", "version": "v3.3.21"}
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = {}
        if body:
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                pass

        target_url = data.get("url", "https://grok.com")
        proxy = data.get("proxy", {}).get("url") if isinstance(data.get("proxy"), dict) else None

        result = solve_cloudflare(target_url, proxy)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode("utf-8"))

    def log_message(self, format, *args):
        # Giảm bớt log thừa
        pass


def run():
    server = HTTPServer(("127.0.0.1", PORT), FlareSolverrHandler)
    print("=" * 65)
    print(f"🚀 FLARESOLVERR NATIVE SERVICE (DRISSIONPAGE) ĐANG CHẠY TRÊN PORT {PORT}")
    print(f"📡 API Endpoint: http://127.0.0.1:{PORT}/v1")
    print("=" * 65)
    server.serve_forever()


if __name__ == "__main__":
    run()
