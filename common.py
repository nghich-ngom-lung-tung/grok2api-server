"""
common.py — Tiện ích dùng chung cho toàn bộ scripts trong repo Grok2API
────────────────────────────────────────────────────────────────────────
- fix_ssl_certs()     : Sửa lỗi SSL cert path chứa ký tự Unicode trên Windows
- setup_console()     : Thiết lập stdout/stderr UTF-8 trên Windows
- get_admin_token()   : Đăng nhập Admin API và trả về JWT access token
- admin_headers()     : Trả về dict headers có sẵn Authorization Bearer
- load_config()       : Đọc credentials từ .env (GROK2API_BASE, GROK2API_USER, GROK2API_PASS)
"""

import os
import sys
import certifi
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))
except ImportError:
    # Tự đọc file .env thủ công nếu chạy bằng python thường chưa cài dotenv
    env_file = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def setup_console():
    """Thiết lập stdout/stderr UTF-8 trên Windows để hiển thị emoji & tiếng Việt."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def fix_ssl_certs():
    """
    Sửa lỗi SSL trên Windows khi đường dẫn certifi chứa ký tự Unicode (như 'nghịch ngợm lung tung').
    Copy cacert.pem vào C:\\Users\\Public\\cacert.pem (100% ASCII path) để curl_cffi không bị crash charmap.
    """
    safe_path = r"C:\Users\Public\cacert.pem"
    try:
        orig = certifi.where()
        if not os.path.exists(safe_path) or os.path.getsize(safe_path) == 0:
            if os.path.exists(os.path.join(SCRIPT_DIR, "cacert.pem")):
                shutil.copy(os.path.join(SCRIPT_DIR, "cacert.pem"), safe_path)
            else:
                shutil.copy(orig, safe_path)
        certifi.where = lambda: safe_path
        os.environ["SSL_CERT_FILE"] = safe_path
        os.environ["REQUESTS_CA_BUNDLE"] = safe_path
        os.environ["CURL_CA_BUNDLE"] = safe_path
    except Exception:
        pass


def _get_env(key, default=""):
    """Đọc biến môi trường, trả về default nếu không có."""
    return os.environ.get(key, default).strip() or default


def get_base_url():
    """Trả về URL gốc của Grok2API server."""
    return _get_env("GROK2API_BASE", "http://127.0.0.1:8080")


def get_admin_credentials():
    """Trả về (username, password) cho Admin API từ .env."""
    return (
        _get_env("GROK2API_USER", "admin"),
        _get_env("GROK2API_PASS", "adminpassword123"),
    )


def get_admin_token(base_url=None):
    """
    Đăng nhập Admin API và trả về JWT access token.
    Trả về None nếu không kết nối được hoặc sai credentials.
    """
    import requests as std_requests

    url = base_url or get_base_url()
    user, pwd = get_admin_credentials()
    try:
        resp = std_requests.post(
            f"{url}/api/admin/v1/auth/login",
            json={"username": user, "password": pwd},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()["data"]["tokens"]["accessToken"]
    except Exception as e:
        print(f"[!] Không thể kết nối tới server Grok2API ({url}): {e}")
    return None


def admin_headers(base_url=None):
    """
    Trả về dict headers có sẵn Authorization Bearer.
    Trả về None nếu không lấy được token.
    """
    token = get_admin_token(base_url)
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


# ─── Tự động khởi tạo khi import ──────────────────────────────────────
setup_console()
fix_ssl_certs()
