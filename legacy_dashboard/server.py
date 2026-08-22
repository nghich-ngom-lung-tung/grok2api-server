"""
Grok Imagine Web Dashboard & OpenAI-Compatible API Server
──────────────────────────────────────────────────────────
- Cổng OpenAI API chuẩn: /v1/images/generations & /v1/chat/completions
- Dashboard Web UI: Thống kê Quota, Lịch sử tạo ảnh, Studio vẽ ảnh trực tiếp, Quản lý kho tài khoản
"""
import os, sys, time, json, random, re, threading, asyncio, secrets, collections
from datetime import datetime
from typing import Optional, List, Dict, Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_DIR = os.path.join(SCRIPT_DIR, "keys")
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
GROK_TXT = os.path.join(KEYS_DIR, "grok.txt")
ACCOUNTS_TXT = os.path.join(KEYS_DIR, "accounts.txt")
HISTORY_JSON = os.path.join(DATA_DIR, "history.json")
REQUEST_LOGS_JSON = os.path.join(DATA_DIR, "request_logs.json")
API_KEYS_JSON = os.path.join(DATA_DIR, "api_keys.json")
AUTH_CONFIG_JSON = os.path.join(DATA_DIR, "auth_config.json")

os.makedirs(KEYS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# ── Load / Save History & Request Logs ──
history_lock = threading.Lock()
req_log_lock = threading.Lock()

def load_history() -> List[Dict[str, Any]]:
    if not os.path.exists(HISTORY_JSON):
        return []
    try:
        with open(HISTORY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history_item(item: Dict[str, Any]):
    with history_lock:
        items = load_history()
        items.insert(0, item)
        items = items[:500]
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

def load_request_logs() -> List[Dict[str, Any]]:
    if not os.path.exists(REQUEST_LOGS_JSON):
        return []
    try:
        with open(REQUEST_LOGS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def log_http_request(client_ip: str, method: str, path: str, status_code: int, duration_ms: float, user_agent: str, detail: str = "", model: str = "-"):
    log_item = {
        "id": f"req_{int(time.time()*1000)}_{random.randint(100,999)}",
        "ip": client_ip,
        "method": method,
        "path": path,
        "model": model,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "user_agent": user_agent[:120],
        "detail": detail,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with req_log_lock:
        logs = load_request_logs()
        logs.insert(0, log_item)
        logs = logs[:1000]  # Giữ 1000 request gần nhất
        try:
            with open(REQUEST_LOGS_JSON, "w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

def load_sso_pool() -> List[str]:
    if not os.path.exists(GROK_TXT):
        return []
    lines = [l.strip() for l in open(GROK_TXT, encoding="utf-8", errors="ignore") if l.strip()]
    return list(dict.fromkeys(lines))  # unique preserving order

# ── Account Pool & Auto-Quota Manager ──
POOL_STATE_JSON = os.path.join(DATA_DIR, "pool_state.json")
DEFAULT_MAX_QUOTA_PER_ACC = 25  # Hạn mức ~20-30 ảnh cho mỗi tài khoản trong khung 2 giờ

class AccountPoolManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.load_state()
        self.sync_from_files()

    def load_state(self):
        if os.path.exists(POOL_STATE_JSON):
            try:
                with open(POOL_STATE_JSON, "r", encoding="utf-8") as f:
                    self.accounts = json.load(f)
            except Exception:
                self.accounts = {}

    def save_state(self):
        try:
            with open(POOL_STATE_JSON, "w", encoding="utf-8") as f:
                json.dump(self.accounts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def sync_from_files(self):
        with self.lock:
            raw_tokens = load_sso_pool()
            acc_map = {}
            if os.path.exists(ACCOUNTS_TXT):
                with open(ACCOUNTS_TXT, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 3:
                            email = parts[0]
                            pwd = parts[1]
                            sso = ":".join(parts[2:])
                            acc_map[sso] = {"email": email, "password": pwd}

            now_ts = int(time.time())
            for idx, token in enumerate(raw_tokens):
                if token not in self.accounts:
                    info = acc_map.get(token, {})
                    email = info.get("email", f"acc_{token[:8]}@mail.tm")
                    self.accounts[token] = {
                        "id": f"acc_{token[:10]}",
                        "sso": token,
                        "email": email,
                        "password": info.get("password", "********"),
                        "type": "Gmail" if "gmail" in email else ("Mail.tm" if "emalupe" in email else "Other"),
                        "status": "HEALTHY",  # HEALTHY (🟢), COOLING (🟡), DEAD (🔴)
                        "max_quota": DEFAULT_MAX_QUOTA_PER_ACC,
                        "used_quota": 0,
                        "remaining_quota": DEFAULT_MAX_QUOTA_PER_ACC,
                        "total_success": 0,
                        "total_failed": 0,
                        "consecutive_fails": 0,
                        "last_used_at": None,
                        "cooldown_until": 0,
                        "window_reset_at": now_ts + 7200,
                        "created_idx": idx
                    }
                else:
                    self.accounts[token]["created_idx"] = idx
                    if token in acc_map and not self.accounts[token].get("email"):
                        self.accounts[token]["email"] = acc_map[token]["email"]
                        self.accounts[token]["password"] = acc_map[token]["password"]
            
            # Tự động hồi phục token nếu tất cả bị đánh dấu DEAD oan
            if self.accounts and not any(a.get("status") == "HEALTHY" for a in self.accounts.values()):
                for a in self.accounts.values():
                    a["status"] = "HEALTHY"
                    a["remaining_quota"] = a.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC)
                    a["consecutive_fails"] = 0
            self.save_state()

    def check_and_reset_windows(self):
        """Tự động kiểm tra và reset quota mỗi khung giờ"""
        now_ts = int(time.time())
        updated = False
        for token, acc in self.accounts.items():
            if now_ts >= acc.get("window_reset_at", 0):
                acc["used_quota"] = 0
                acc["remaining_quota"] = acc.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC)
                acc["window_reset_at"] = now_ts + 7200
                if acc.get("status") in ["COOLING", "DEAD"]:
                    acc["status"] = "HEALTHY"
                    acc["cooldown_until"] = 0
                    acc["consecutive_fails"] = 0
                updated = True
            elif acc.get("status") == "COOLING" and now_ts >= acc.get("cooldown_until", 0):
                acc["status"] = "HEALTHY"
                acc["cooldown_until"] = 0
                updated = True
        if updated:
            self.save_state()

    def get_best_token(self, exclude_tokens: List[str] = None) -> Optional[str]:
        """Thuật toán chọn tài khoản tối ưu (còn nhiều quota nhất + ưu tiên tài khoản mới nhất)"""
        with self.lock:
            self.check_and_reset_windows()
            exclude_set = set(exclude_tokens or [])
            healthy_accs = [
                acc for acc in self.accounts.values()
                if acc.get("status") == "HEALTHY" and acc.get("remaining_quota", 0) > 0 and acc["sso"] not in exclude_set
            ]
            if not healthy_accs:
                available = [
                    acc for acc in self.accounts.values() 
                    if acc["sso"] not in exclude_set
                ]
                if not available:
                    # Nếu mọi token đều trong exclude, lấy lại token bất kỳ
                    available = list(self.accounts.values())
                    if not available:
                        return None
                healthy_accs = available

            # Ưu tiên tài khoản mới reg gần nhất, sau đó đến còn nhiều quota nhất
            healthy_accs.sort(key=lambda x: (-x.get("created_idx", 0), -x.get("remaining_quota", 0), x.get("used_quota", 0)))
            return healthy_accs[0]["sso"]

    def record_success(self, sso_token: str, duration: float):
        with self.lock:
            if sso_token in self.accounts:
                acc = self.accounts[sso_token]
                acc["used_quota"] = acc.get("used_quota", 0) + 1
                acc["remaining_quota"] = max(0, acc.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC) - acc["used_quota"])
                acc["total_success"] = acc.get("total_success", 0) + 1
                acc["consecutive_fails"] = 0
                acc["last_used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if acc["remaining_quota"] <= 0:
                    acc["status"] = "COOLING"
                    acc["cooldown_until"] = int(time.time()) + 7200
                self.save_state()

    def record_rate_limit(self, sso_token: str):
        with self.lock:
            if sso_token in self.accounts:
                acc = self.accounts[sso_token]
                acc["status"] = "COOLING"
                acc["used_quota"] = acc.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC)
                acc["remaining_quota"] = 0
                acc["cooldown_until"] = int(time.time()) + 7200
                self.save_state()

    def record_fail(self, sso_token: str, error_msg: str = ""):
        with self.lock:
            if sso_token in self.accounts:
                acc = self.accounts[sso_token]
                acc["total_failed"] = acc.get("total_failed", 0) + 1
                acc["consecutive_fails"] = acc.get("consecutive_fails", 0) + 1
                if "expired" in error_msg.lower() or "not found" in error_msg.lower() or acc["consecutive_fails"] >= 2:
                    acc["status"] = "DEAD"
                self.save_state()

    def get_pool_summary(self) -> Dict[str, Any]:
        with self.lock:
            self.check_and_reset_windows()
            total_accs = len(self.accounts)
            healthy = sum(1 for a in self.accounts.values() if a.get("status") == "HEALTHY")
            cooling = sum(1 for a in self.accounts.values() if a.get("status") == "COOLING")
            dead = sum(1 for a in self.accounts.values() if a.get("status") == "DEAD")
            
            total_capacity = sum(a.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC) for a in self.accounts.values() if a.get("status") != "DEAD")
            total_used = sum(a.get("used_quota", 0) for a in self.accounts.values() if a.get("status") != "DEAD")
            total_remaining = max(0, total_capacity - total_used)
            
            utilization_pct = round((total_used / total_capacity * 100), 1) if total_capacity > 0 else 0

            return {
                "total_accounts": total_accs,
                "healthy_count": healthy,
                "cooling_count": cooling,
                "dead_count": dead,
                "total_pool_capacity": total_capacity,
                "total_pool_used": total_used,
                "total_pool_remaining": total_remaining,
                "utilization_pct": utilization_pct,
                "auto_replenish_needed": total_remaining < 50 or healthy < 3,
                "accounts": list(self.accounts.values())
            }

    def reset_all_quotas(self):
        with self.lock:
            now_ts = int(time.time())
            for acc in self.accounts.values():
                acc["used_quota"] = 0
                acc["remaining_quota"] = acc.get("max_quota", DEFAULT_MAX_QUOTA_PER_ACC)
                acc["status"] = "HEALTHY"
                acc["cooldown_until"] = 0
                acc["consecutive_fails"] = 0
                acc["window_reset_at"] = now_ts + 7200
            self.save_state()

    def clean_dead_tokens(self) -> Dict[str, Any]:
        """Lọc và xóa toàn bộ token DEAD khỏi Pool và file keys/grok.txt"""
        with self.lock:
            dead_tokens = [tok for tok, a in self.accounts.items() if a.get("status") == "DEAD"]
            for tok in dead_tokens:
                del self.accounts[tok]

            alive_tokens = list(self.accounts.keys())
            try:
                with open(GROK_TXT, "w", encoding="utf-8") as f:
                    for tok in alive_tokens:
                        f.write(tok.strip() + "\n")
            except Exception:
                pass

            self.save_state()
            return {
                "status": "ok",
                "removed_count": len(dead_tokens),
                "remaining_count": len(alive_tokens),
                "message": f"Đã dọn sạch {len(dead_tokens)} token chết. Còn lại {len(alive_tokens)} token khả dụng."
            }

    def scan_all_tokens_health(self) -> Dict[str, Any]:
        """Quét và phân loại sức khỏe toàn bộ token trong Pool"""
        from DrissionPage import ChromiumPage, ChromiumOptions
        tokens_to_scan = list(self.accounts.keys())
        healthy_found = 0
        dead_found = 0

        co = ChromiumOptions()
        co.auto_port()
        co.set_argument("--window-position=-32000,-32000")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome", "health_scan")
        os.makedirs(temp_dir, exist_ok=True)
        co.set_argument(f"--user-data-dir={temp_dir}")

        page = None
        try:
            page = ChromiumPage(co)
            for tok in tokens_to_scan:
                try:
                    page.get("https://grok.com", timeout=12)
                    page.set.cookies({"name": "sso", "value": tok, "domain": ".grok.com", "path": "/"})
                    page.set.cookies({"name": "sso-rw", "value": tok, "domain": ".grok.com", "path": "/"})
                    page.get("https://grok.com", timeout=12)
                    time.sleep(1.5)

                    url = (page.url or "").lower()
                    if "signin" in url or "login" in url or "register" in url or "logout" in url:
                        with self.lock:
                            if tok in self.accounts:
                                self.accounts[tok]["status"] = "DEAD"
                        dead_found += 1
                    else:
                        with self.lock:
                            if tok in self.accounts and self.accounts[tok].get("status") == "DEAD":
                                self.accounts[tok]["status"] = "HEALTHY"
                        healthy_found += 1
                except Exception:
                    pass
        finally:
            if page:
                try: page.quit()
                except Exception: pass

        self.save_state()
        return {
            "status": "ok",
            "total_scanned": len(tokens_to_scan),
            "healthy": healthy_found,
            "dead": dead_found,
            "message": f"Quét hoàn tất: {healthy_found} tài khoản khỏe, {dead_found} tài khoản hết hạn/chết."
        }

    def keep_alive_all_healthy(self) -> Dict[str, Any]:
        """Gửi tín hiệu nuôi session (Keep-Alive) cho các token Healthy để kéo dài hạn cookie"""
        from DrissionPage import ChromiumPage, ChromiumOptions
        healthy_tokens = [tok for tok, a in self.accounts.items() if a.get("status") == "HEALTHY"]
        if not healthy_tokens:
            return {"status": "ok", "touched_count": 0, "message": "Không có token nào ở trạng thái Healthy để nuôi."}

        co = ChromiumOptions()
        co.auto_port()
        co.set_argument("--window-position=-32000,-32000")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome", "keep_alive")
        os.makedirs(temp_dir, exist_ok=True)
        co.set_argument(f"--user-data-dir={temp_dir}")

        touched = 0
        page = None
        try:
            page = ChromiumPage(co)
            for tok in healthy_tokens[:10]:  # Nuôi 10 token ưu tiên mỗi đợt
                try:
                    page.get("https://grok.com", timeout=12)
                    page.set.cookies({"name": "sso", "value": tok, "domain": ".grok.com", "path": "/"})
                    page.set.cookies({"name": "sso-rw", "value": tok, "domain": ".grok.com", "path": "/"})
                    page.get("https://grok.com", timeout=12)
                    time.sleep(2)
                    touched += 1
                except Exception:
                    pass
        finally:
            if page:
                try: page.quit()
                except Exception: pass

        return {
            "status": "ok",
            "touched_count": touched,
            "message": f"Đã nuôi và gia hạn session thành công cho {touched} tài khoản."
        }

    def auto_relogin_dead_accounts(self, max_count: int = 5) -> Dict[str, Any]:
        """Tự động đăng nhập lại các nick cũ trong accounts.txt để lấy Session SSO mới toanh"""
        from DrissionPage import ChromiumPage, ChromiumOptions
        
        targets = []
        if os.path.exists(ACCOUNTS_TXT):
            with open(ACCOUNTS_TXT, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 3:
                        email, pwd = parts[0], parts[1]
                        old_sso = ":".join(parts[2:])
                        if old_sso in self.accounts and self.accounts[old_sso].get("status") == "DEAD":
                            targets.append({"email": email, "password": pwd, "old_sso": old_sso})
                        elif old_sso not in self.accounts:
                            targets.append({"email": email, "password": pwd, "old_sso": old_sso})
        
        if not targets:
            return {"status": "ok", "refreshed_count": 0, "message": "Không tìm thấy tài khoản chết nào cần đăng nhập lại."}
            
        targets = targets[:max_count]
        refreshed_count = 0
        
        co = ChromiumOptions()
        co.auto_port()
        co.set_argument("--window-position=-32000,-32000")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        
        page = None
        try:
            page = ChromiumPage(co)
            for acc in targets:
                try:
                    email = acc["email"]
                    pwd = acc["password"]
                    page.get("https://grok.com", timeout=15)
                    time.sleep(2)
                    
                    signin_btn = page.ele("@text*Sign In") or page.ele("@text*Log in") or page.ele("@text*Đăng nhập") or page.ele("tag:a@href*sign-in")
                    if signin_btn:
                        signin_btn.click()
                        time.sleep(2)
                        
                    email_inp = page.ele("@type=email") or page.ele("@placeholder*email") or page.ele("@name=email")
                    if email_inp:
                        email_inp.input(f"{email}\n")
                        time.sleep(2)
                        
                    pwd_inp = page.ele("@type=password") or page.ele("@placeholder*password") or page.ele("@name=password")
                    if pwd_inp:
                        pwd_inp.input(f"{pwd}\n")
                        time.sleep(3)
                        
                    cookies = page.cookies()
                    new_sso = None
                    for c in cookies:
                        if c.get("name") == "sso":
                            new_sso = c.get("value")
                            break
                            
                    if new_sso and new_sso != acc.get("old_sso"):
                        refreshed_count += 1
                        with self.lock:
                            old_sso = acc.get("old_sso")
                            if old_sso in self.accounts:
                                del self.accounts[old_sso]
                            self.accounts[new_sso] = {
                                "id": f"acc_{new_sso[:10]}",
                                "sso": new_sso,
                                "email": email,
                                "password": pwd,
                                "type": "Mail.tm" if "emalupe" in email else "Other",
                                "status": "HEALTHY",
                                "max_quota": DEFAULT_MAX_QUOTA_PER_ACC,
                                "used_quota": 0,
                                "remaining_quota": DEFAULT_MAX_QUOTA_PER_ACC,
                                "total_success": 0,
                                "total_failed": 0,
                                "consecutive_fails": 0,
                                "last_used_at": None,
                                "cooldown_until": 0,
                                "window_reset_at": int(time.time()) + 7200,
                                "created_idx": 9999
                            }
                except Exception:
                    pass
        finally:
            if page:
                try: page.quit()
                except Exception: pass
                
        if refreshed_count > 0:
            self.save_state()
            try:
                with open(GROK_TXT, "w", encoding="utf-8") as f:
                    for tok in self.accounts.keys():
                        f.write(tok.strip() + "\n")
            except Exception:
                pass
                    
        return {
            "status": "ok",
            "refreshed_count": refreshed_count,
            "message": f"Đã đăng nhập lại và lấy thành công {refreshed_count} Session Token mới!"
        }

def remove_grok_watermark(image_path: str, output_path: str = None) -> str:
    """
    Tự động phát hiện và xóa sạch watermark Grok ở góc dưới bên phải
    bằng thuật toán Fast Adaptive Inpainting (giữ nguyên 100% độ sắc nét).
    """
    try:
        import cv2
        import numpy as np

        if output_path is None:
            output_path = image_path

        # OpenCV không đọc được đường dẫn Unicode trên Windows
        # → dùng numpy buffer để bypass
        with open(image_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[!] Không decode được ảnh: {image_path}")
            return image_path

        h, w, c = img.shape
        pad_w = int(w * 0.16)
        pad_h = int(h * 0.05)
        pad_w = max(110, min(pad_w, 200))
        pad_h = max(35, min(pad_h, 75))

        x1 = max(0, w - pad_w)
        y1 = max(0, h - pad_h)
        x2 = w
        y2 = h

        roi = img[y1:y2, x1:x2]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        tophat = cv2.morphologyEx(gray_roi, cv2.MORPH_TOPHAT, kernel)
        _, thresh = cv2.threshold(tophat, 25, 255, cv2.THRESH_BINARY)
        
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated = cv2.dilate(thresh, dilate_kernel, iterations=2)

        if cv2.countNonZero(dilated) < 30:
            dilated = np.ones_like(gray_roi) * 255

        full_mask = np.zeros((h, w), dtype=np.uint8)
        full_mask[y1:y2, x1:x2] = dilated

        result = cv2.inpaint(img, full_mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)
        # Ghi file bằng numpy buffer để hỗ trợ Unicode path
        success, encoded = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 96])
        if success:
            with open(output_path, "wb") as f:
                f.write(encoded.tobytes())
            print(f"[✓] Watermark đã xóa thành công: {os.path.basename(output_path)}")
        return output_path
    except Exception as e:
        print(f"[!] Lỗi xóa watermark: {e}")
        return image_path

pool_manager = AccountPoolManager()

# ── API Key & Rate Limiting Engine ──
class ApiKeyManager:
    """Quản lý danh sách API Key và cấu hình bảo mật hệ thống"""
    def __init__(self):
        self.lock = threading.Lock()
        self.keys: List[Dict[str, Any]] = []
        self.config: Dict[str, Any] = {
            "require_auth": os.getenv("API_AUTH_ENABLED", "false").lower() in ("true", "1", "yes"),
            "global_rate_limit_rpm": int(os.getenv("GLOBAL_RATE_LIMIT_RPM", "60"))
        }
        self.load()

    def load(self):
        with self.lock:
            if os.path.exists(AUTH_CONFIG_JSON):
                try:
                    with open(AUTH_CONFIG_JSON, "r", encoding="utf-8") as f:
                        self.config.update(json.load(f))
                except Exception:
                    pass
            if os.path.exists(API_KEYS_JSON):
                try:
                    with open(API_KEYS_JSON, "r", encoding="utf-8") as f:
                        self.keys = json.load(f)
                except Exception:
                    self.keys = []
            
            # Tự động tạo 1 Master API Key mặc định nếu kho key đang trống
            if not self.keys:
                default_k = f"grok-sk-{secrets.token_hex(16)}"
                self.keys.append({
                    "id": f"key_{int(time.time()*1000)}",
                    "name": "Default Master Key",
                    "key": default_k,
                    "status": "active",
                    "rate_limit_rpm": 60,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_used_at": None,
                    "total_requests": 0
                })
                self._save_keys_unlocked()

    def _save_config_unlocked(self):
        try:
            with open(AUTH_CONFIG_JSON, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _save_keys_unlocked(self):
        try:
            with open(API_KEYS_JSON, "w", encoding="utf-8") as f:
                json.dump(self.keys, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_config(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.config)

    def update_config(self, require_auth: Optional[bool] = None, global_rate_limit_rpm: Optional[int] = None) -> Dict[str, Any]:
        with self.lock:
            if require_auth is not None:
                self.config["require_auth"] = bool(require_auth)
            if global_rate_limit_rpm is not None:
                self.config["global_rate_limit_rpm"] = max(1, int(global_rate_limit_rpm))
            self._save_config_unlocked()
            return dict(self.config)

    def get_keys(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [dict(k) for k in self.keys]

    def create_key(self, name: str, rate_limit_rpm: int = 30, custom_key: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            key_token = custom_key.strip() if custom_key and custom_key.strip() else f"grok-sk-{secrets.token_hex(16)}"
            new_item = {
                "id": f"key_{int(time.time()*1000)}_{random.randint(100, 999)}",
                "name": name.strip() or "API Key",
                "key": key_token,
                "status": "active",
                "rate_limit_rpm": max(0, int(rate_limit_rpm)),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_used_at": None,
                "total_requests": 0
            }
            self.keys.insert(0, new_item)
            self._save_keys_unlocked()
            return new_item

    def delete_key(self, key_id: str) -> bool:
        with self.lock:
            orig_len = len(self.keys)
            self.keys = [k for k in self.keys if k["id"] != key_id and k["key"] != key_id]
            if len(self.keys) < orig_len:
                self._save_keys_unlocked()
                return True
            return False

    def toggle_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            for k in self.keys:
                if k["id"] == key_id or k["key"] == key_id:
                    k["status"] = "disabled" if k.get("status") == "active" else "active"
                    self._save_keys_unlocked()
                    return dict(k)
            return None

    def validate_key(self, token: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            for k in self.keys:
                if k.get("key") == token and k.get("status") == "active":
                    k["last_used_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    k["total_requests"] = k.get("total_requests", 0) + 1
                    self._save_keys_unlocked()
                    return dict(k)
            return None

class RateLimiter:
    """Sliding Window Rate Limiter (Thread-safe) giới hạn số Request/Phút theo IP hoặc Key"""
    def __init__(self):
        self.lock = threading.Lock()
        self.history: Dict[str, List[float]] = collections.defaultdict(list)

    def check(self, identifier: str, limit_rpm: int) -> tuple:
        now = time.time()
        window = 60.0
        with self.lock:
            timestamps = [t for t in self.history[identifier] if now - t < window]
            self.history[identifier] = timestamps
            
            if len(timestamps) >= limit_rpm:
                oldest = timestamps[0]
                retry_after = max(1, int(window - (now - oldest)))
                return False, 0, retry_after
            
            self.history[identifier].append(now)
            remaining = max(0, limit_rpm - len(self.history[identifier]))
            return True, remaining, 0

api_key_manager = ApiKeyManager()
rate_limiter = RateLimiter()

def extract_api_key(request: Request) -> Optional[str]:
    """Trích xuất API Key từ Authorization header, x-api-key hoặc query params"""
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header:
        parts = auth_header.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        if len(parts) == 1 and not parts[0].lower().startswith("bearer"):
            return parts[0].strip()
    x_api_key = request.headers.get("x-api-key", "").strip()
    if x_api_key:
        return x_api_key
    q_key = request.query_params.get("api_key", "").strip()
    if q_key:
        return q_key
    return None

def verify_auth_and_rate_limit(request: Request) -> Optional[Dict[str, Any]]:
    """Xác thực Bearer API Key và kiểm tra giới hạn Rate Limit (RPM)"""
    client_ip = get_real_client_ip(request)
    auth_config = api_key_manager.get_config()
    require_auth = auth_config.get("require_auth", False)
    global_rpm = auth_config.get("global_rate_limit_rpm", 60)

    token = extract_api_key(request)
    key_obj = None

    if token:
        key_obj = api_key_manager.validate_key(token)
        if not key_obj and require_auth:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "Sai API Key hoặc Key đã bị vô hiệu hóa. Vui lòng kiểm tra API Key trong Grok Dashboard.",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key"
                    }
                }
            )
    elif require_auth:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Yêu cầu API Key để truy cập. Vui lòng truyền header 'Authorization: Bearer <your_api_key>'.",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "missing_api_key"
                }
            }
        )

    # Xác định mức giới hạn RPM
    if key_obj:
        rpm = key_obj.get("rate_limit_rpm", 30)
        limiter_id = f"key:{key_obj['id']}"
    else:
        rpm = global_rpm
        limiter_id = f"ip:{client_ip}"

    # Kiểm tra Rate Limit (nếu rpm > 0, 0 = không giới hạn)
    if rpm > 0:
        is_allowed, remaining, retry_after = rate_limiter.check(limiter_id, rpm)
        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "message": f"Vượt quá giới hạn request ({rpm} request/phút). Vui lòng thử lại sau {retry_after} giây.",
                        "type": "requests",
                        "param": None,
                        "code": "rate_limit_exceeded"
                    }
                },
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(rpm), "X-RateLimit-Remaining": "0"}
            )

    return key_obj

def get_next_sso_token() -> Optional[str]:
    return pool_manager.get_best_token()

# ── Image Generation Engine (Thread-safe) ──
gen_lock = threading.Lock()

def do_generate_image(prompt: str, sso_token: str = None) -> Optional[Dict[str, Any]]:
    from DrissionPage import ChromiumPage, ChromiumOptions
    
    tried_tokens = []
    max_retries = 3
    
    for attempt in range(max_retries):
        current_token = sso_token if (sso_token and attempt == 0) else pool_manager.get_best_token(exclude_tokens=tried_tokens)
        if not current_token:
            raise ValueError("Không còn tài khoản khả dụng trong Pool!")
            
        tried_tokens.append(current_token)
        t0 = time.time()
        co = ChromiumOptions()
        co.auto_port()
        temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome", f"gen_{int(time.time()*1000)}_{random.randint(1000, 9999)}")
        os.makedirs(temp_dir, exist_ok=True)
        co.set_argument(f"--user-data-dir={temp_dir}")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--no-sandbox")
        co.set_argument("--window-size=1280,900")
        
        page = ChromiumPage(co)
        img_url = None
        try:
            # 1. Nạp cookie vào grok.com
            page.get("https://grok.com", timeout=15)
            page.set.cookies({"name": "sso", "value": current_token, "domain": ".grok.com", "path": "/"})
            page.set.cookies({"name": "sso-rw", "value": current_token, "domain": ".grok.com", "path": "/"})
            page.get("https://grok.com/imagine", timeout=25)

            # 2. Xử lý triệt để tất cả Modal & Popup trước khi tìm input_box (Age, Cookies, Promo, SuperGrok Subscribe)
            for _ in range(8):
                time.sleep(0.4)
                try:
                    page.run_js('''
                        if (!document.body) return;
                        var allBtns = Array.from(document.querySelectorAll('button'));
                        
                        // Age Confirmation Modal
                        var contBtn = allBtns.find(b => (b.innerText || '').trim().toLowerCase() === 'continue');
                        if (contBtn) contBtn.click();
                        
                        // Cookie Banner Accept
                        var cookieBtn = document.querySelector('#onetrust-accept-btn-handler') || 
                                        allBtns.find(b => (b.innerText || '').includes('Accept All Cookies'));
                        if (cookieBtn) cookieBtn.click();
                        
                        // Promo Banner & Subscribe close
                        allBtns.forEach(function(b) {
                            var aria = b.getAttribute('aria-label') || '';
                            var t = (b.innerText || '').trim().toLowerCase();
                            if (aria === 'Close' || aria === 'Dismiss' || t === 'try it out' || t === 'dismiss' || t === 'close') {
                                b.click();
                            }
                        });
                        
                        // Xóa các overlay che chắn
                        var overlays = document.querySelectorAll('[role="dialog"], #onetrust-banner-sdk, .onetrust-pc-dark-filter');
                        overlays.forEach(function(o) {
                            if (o.innerText && (o.innerText.includes('SuperGrok') || o.innerText.includes('cookies'))) {
                                o.remove();
                            }
                        });
                        document.body.style.overflow = 'auto';
                    ''')
                except Exception:
                    pass

            # 3. Đợi ô nhập prompt /imagine sẵn sàng
            input_box = (
                page.ele(".ProseMirror", timeout=20)
                or page.ele("@contenteditable=true", timeout=10)
                or page.ele("tag:textarea", timeout=10)
                or page.ele("@placeholder*Ask", timeout=5)
                or page.ele("@placeholder*Imagine", timeout=5)
                or page.ele("@placeholder*anything", timeout=5)
            )

            # Kiểm tra xem có bị đẩy ra trang Login / Signin không
            curr_url = (page.url or "").lower()
            if "signin" in curr_url or "login" in curr_url or "register" in curr_url:
                print(f"[Pool] ⚠️ Token {current_token[:15]}... đã hết hạn session. Đang tự động chuyển sang token khác...")
                pool_manager.record_fail(current_token, "Token expired")
                continue

            if not input_box:
                print(f"[Pool] ⚠️ Không tìm thấy ô nhập prompt trên Grok với token {current_token[:15]}... Thử token tiếp theo...")
                pool_manager.record_fail(current_token, "Input not found")
                continue

            # 4. Snapshot các ảnh đã tạo trước đó của tài khoản này
            pre_urls = set()
            try:
                pre_urls_js = page.run_js('''
                    var urls = [];
                    document.querySelectorAll('img').forEach(function(img) {
                        var s = img.src || img.currentSrc || '';
                        if (s && s.includes('assets.grok.com') && s.includes('/generated/')) {
                            urls.push(s);
                        }
                    });
                    return JSON.stringify(urls);
                ''')
                if pre_urls_js:
                    pre_urls = set(json.loads(str(pre_urls_js)))
            except Exception:
                pass
            print(f"[Gen] Snapshot {len(pre_urls)} ảnh /generated/ có sẵn trước khi submit")

            # 5. Nhập prompt
            try:
                input_box.click()
                time.sleep(0.3)
            except Exception:
                pass

            input_box.input(f"{prompt}")
            time.sleep(1)

            # Dismiss Age modal nếu xuất hiện khi focus
            try:
                page.run_js('''
                    var allBtns = Array.from(document.querySelectorAll('button'));
                    var contBtn = allBtns.find(b => (b.innerText || '').trim().toLowerCase() === 'continue');
                    if (contBtn) contBtn.click();
                ''')
            except Exception:
                pass
            time.sleep(0.5)

            # 6. Bấm Submit
            send_btn = (
                page.ele("@aria-label=Submit")
                or page.ele("@aria-label*Submit")
                or page.ele("@type=submit")
                or page.ele("tag:button@aria-label*Generate")
                or page.ele("@aria-label*Send")
            )
            if send_btn:
                try: send_btn.click()
                except Exception: input_box.input("\n")
            else:
                input_box.input("\n")

            # Giải phóng modal xác nhận tuổi xuất hiện ngay sau khi submit
            for _ in range(10):
                time.sleep(0.4)
                try:
                    page.run_js('''
                        var allBtns = Array.from(document.querySelectorAll('button'));
                        var contBtn = allBtns.find(b => (b.innerText || '').trim().toLowerCase() === 'continue');
                        if (contBtn) contBtn.click();
                        var cookieBtn = document.querySelector('#onetrust-accept-btn-handler') || 
                                        allBtns.find(b => (b.innerText || '').includes('Accept All Cookies'));
                        if (cookieBtn) cookieBtn.click();
                    ''')
                except Exception:
                    pass

            # 7. Đợi kết quả ảnh FLUX.1 MỚI (tối đa 100s)
            print(f"[Gen] Đang đợi Grok FLUX.1 sinh ảnh cho prompt: '{prompt[:40]}...'")
            for wait_i in range(50):
                time.sleep(2)
                try:
                    curr_urls_js = page.run_js('''
                        var urls = [];
                        document.querySelectorAll('img').forEach(function(img) {
                            var s = img.src || img.currentSrc || '';
                            if (s && s.includes('assets.grok.com') && s.includes('/generated/')) {
                                urls.push(s);
                            }
                        });
                        return JSON.stringify(urls);
                    ''')
                    if curr_urls_js:
                        curr_urls = json.loads(str(curr_urls_js))
                        new_urls = [u for u in curr_urls if u not in pre_urls]
                        if new_urls:
                            img_url = new_urls[-1]
                            print(f"[Gen] ✅ Đã tạo thành công ảnh FLUX.1 mới sau {(wait_i+1)*2}s: {img_url[:80]}...")
                            break
                    
                    if (wait_i + 1) % 5 == 0:
                        print(f"[Gen] ⏳ Đang render AI FLUX.1... ({(wait_i+1)*2}s / 100s)")
                except Exception as e:
                    pass
                if img_url:
                    break
        finally:
            if page:
                try: page.quit()
                except Exception: pass
            try:
                import shutil
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        elapsed = round(time.time() - t0, 2)
        if img_url:
            pool_manager.record_success(current_token, elapsed)
            img_id = f"img_{int(time.time()*1000)}"
            local_filename = f"{img_id}.jpg"
            local_dir = os.path.join(STATIC_DIR, "generated_images")
            os.makedirs(local_dir, exist_ok=True)
            local_filepath = os.path.join(local_dir, local_filename)
            
            display_url = f"/static/generated_images/{local_filename}"
            try:
                import urllib.request
                req = urllib.request.Request(
                    img_url,
                    headers={
                        "Cookie": f"sso={current_token}; sso-rw={current_token}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                        "Referer": "https://grok.com/"
                    }
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    with open(local_filepath, "wb") as out_file:
                        out_file.write(resp.read())
                # ✨ Tự động xóa watermark Grok khỏi ảnh
                try:
                    remove_grok_watermark(local_filepath)
                    print(f"[✓] Đã xóa watermark Grok: {local_filename}")
                except Exception as wm_err:
                    print(f"[!] Không xóa được watermark: {wm_err}")
            except Exception as e:
                print(f"[!] Lỗi tải ảnh về máy: {e}")
                display_url = img_url

            result_item = {
                "id": img_id,
                "prompt": prompt,
                "url": display_url,
                "upstream_url": img_url,
                "sso_preview": current_token[:15] + "...",
                "duration": elapsed,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success"
            }
            save_history_item(result_item)
            return result_item
        else:
            pool_manager.record_fail(current_token, "Không tìm thấy link ảnh")

    fail_item = {
        "id": f"img_{int(time.time()*1000)}",
        "prompt": prompt,
        "url": None,
        "sso_preview": "N/A",
        "duration": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "failed"
    }
    save_history_item(fail_item)
    return None

# ── FastAPI App ──
app = FastAPI(
    title="Grok Imagine Dashboard & API Gateway",
    description="OpenAI-compatible Image Generation API & Real-time Dashboard for Grok",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Đảm bảo mọi lỗi HTTP đều trả về đúng chuẩn JSON Payload của OpenAI API"""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "type": "invalid_request_error" if exc.status_code < 500 else "api_error",
                "param": None,
                "code": "error"
            }
        },
        headers=exc.headers
    )

def get_real_client_ip(request: Request) -> str:
    """Bắt chính xác địa chỉ IP của Client (kể cả qua Cloudflare Tunnel, Nginx, Reverse Proxy)"""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    x_forwarded = request.headers.get("x-forwarded-for")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    x_real = request.headers.get("x-real-ip")
    if x_real:
        return x_real.strip()
    return request.client.host if request.client else "127.0.0.1"

@app.middleware("http")
async def request_monitor_middleware(request: Request, call_next):
    """Middleware tự động theo dõi, tính latency và lưu mọi HTTP Request kèm Model đã gọi"""
    start_t = time.time()
    client_ip = get_real_client_ip(request)
    method = request.method
    path = request.url.path
    user_agent = request.headers.get("user-agent", "Unknown")

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except HTTPException as he:
        status_code = he.status_code
        raise he
    except Exception as exc:
        status_code = 500
        raise exc
    finally:
        duration_ms = round((time.time() - start_t) * 1000, 1)
        # Bỏ qua log file tĩnh static/ (css, js) để bảng theo dõi gọn gàng
        if not path.startswith("/static/"):
            model = getattr(request.state, "model", None)
            if not model:
                if path == "/api/draw":
                    model = "grok-imagine-image-2.0"
                elif path == "/v1/images/generations":
                    model = "grok-imagine-image"
                elif path == "/v1/chat/completions":
                    model = "grok-3"
                elif path.startswith("/api/pool"):
                    model = "System / Pool"
                elif path.startswith("/api/security"):
                    model = "Security / Key"
                elif path in ["/api/stats", "/api/models", "/api/history", "/api/request-stats", "/api/request-logs", "/"]:
                    model = "Dashboard"
                else:
                    model = "-"

            log_http_request(
                client_ip=client_ip,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                user_agent=user_agent,
                model=model
            )

# ── Pydantic Request Models ──
class ImageGenRequest(BaseModel):
    prompt: str
    model: Optional[str] = "grok-imagine-image"
    n: Optional[int] = 1
    size: Optional[str] = "1024x1024"
    response_format: Optional[str] = "url"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "grok-imagine-image"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7

class DirectDrawRequest(BaseModel):
    prompt: str
    model: Optional[str] = "grok-imagine-image-2.0"

class CreateApiKeyRequest(BaseModel):
    name: str
    rate_limit_rpm: Optional[int] = 30
    custom_key: Optional[str] = None

class UpdateSecurityConfigRequest(BaseModel):
    require_auth: Optional[bool] = None
    global_rate_limit_rpm: Optional[int] = None

# ── Model Registry & Specifications ──
AVAILABLE_MODELS = [
    {
        "id": "grok-imagine-image",
        "name": "Grok Imagine Image (FLUX.1)",
        "type": "image",
        "owned_by": "xai",
        "description": "Model tạo ảnh chính thức của Grok dựa trên FLUX.1 (Text-to-Image)",
        "badge": "KHUYÊN DÙNG"
    },
    {
        "id": "grok-imagine-image-2.0",
        "name": "Grok Imagine Image 2.0 (HD)",
        "type": "image",
        "owned_by": "xai",
        "description": "Bản nâng cấp tạo ảnh siêu thực với độ chi tiết cao và chiều sâu",
        "badge": "HD ULTRA"
    },
    {
        "id": "grok-imagine-image-edit",
        "name": "Grok Imagine Image Edit",
        "type": "image",
        "owned_by": "xai",
        "description": "Model chỉnh sửa, inpainting và tạo biến thể hình ảnh",
        "badge": "EDIT"
    },
    {
        "id": "grok-2-image",
        "name": "Grok 2 Image",
        "type": "image",
        "owned_by": "xai",
        "description": "Model tạo ảnh thế hệ 2 tiêu chuẩn của xAI",
        "badge": "GEN 2"
    },
    {
        "id": "grok-3",
        "name": "Grok 3 (Flagship)",
        "type": "chat",
        "owned_by": "xai",
        "description": "Model flagship thông minh nhất của xAI với khả năng suy luận và tạo ảnh",
        "badge": "FLAGSHIP"
    },
    {
        "id": "grok-3-mini",
        "name": "Grok 3 Mini",
        "type": "chat",
        "owned_by": "xai",
        "description": "Model phản hồi nhanh, nhẹ và tiết kiệm tài nguyên",
        "badge": "FAST"
    },
    {
        "id": "grok-4.5",
        "name": "Grok 4.5 (1M Context)",
        "type": "chat",
        "owned_by": "xai",
        "description": "Model xử lý ngữ cảnh cực lớn lên tới 1 triệu tokens",
        "badge": "1M TOKENS"
    },
    {
        "id": "grok-4.6",
        "name": "Grok 4.6 (Reasoning)",
        "type": "chat",
        "owned_by": "xai",
        "description": "Model suy luận logic và giải toán chuyên sâu",
        "badge": "REASONING"
    },
    {
        "id": "grok-chat-fast",
        "name": "Grok Chat Fast",
        "type": "chat",
        "owned_by": "xai",
        "description": "Model chat tốc độ cao tối ưu cho tương tác real-time",
        "badge": "REALTIME"
    }
]

# ── API Endpoints ──

@app.get("/v1/models")
def get_v1_models(request: Request):
    """Endpoint chuẩn OpenAI trả về danh sách toàn bộ model có thể sử dụng"""
    cfg = api_key_manager.get_config()
    if cfg.get("require_auth"):
        verify_auth_and_rate_limit(request)
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": 1723990000,
                "owned_by": m.get("owned_by", "xai"),
                "permission": [],
                "root": m["id"],
                "parent": None
            }
            for m in AVAILABLE_MODELS
        ]
    }

@app.get("/api/models")
def get_api_models():
    """Endpoint trả về chi tiết model kèm mô tả và phân loại cho Web UI"""
    return {
        "total": len(AVAILABLE_MODELS),
        "models": AVAILABLE_MODELS
    }

# ── Security & API Key Management Endpoints ──

@app.get("/api/security/config")
def get_security_config():
    """Lấy cấu hình bảo mật và trạng thái bắt buộc API Key"""
    return api_key_manager.get_config()

@app.post("/api/security/config")
def update_security_config(req: UpdateSecurityConfigRequest):
    """Bật / Tắt xác thực API Key hoặc đổi giới hạn Rate Limit toàn cục"""
    cfg = api_key_manager.update_config(
        require_auth=req.require_auth,
        global_rate_limit_rpm=req.global_rate_limit_rpm
    )
    return {"status": "ok", "config": cfg}

@app.get("/api/security/keys")
def get_security_keys():
    """Lấy danh sách tất cả API Key hiện có"""
    keys = api_key_manager.get_keys()
    return {"total": len(keys), "keys": keys}

@app.post("/api/security/keys")
def create_security_key(req: CreateApiKeyRequest):
    """Tạo API Key mới với tên và giới hạn RPM tùy chỉnh"""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Tên API Key không được để trống")
    item = api_key_manager.create_key(
        name=req.name.strip(),
        rate_limit_rpm=req.rate_limit_rpm or 30,
        custom_key=req.custom_key
    )
    return {"status": "ok", "key": item}

@app.delete("/api/security/keys/{key_id}")
def delete_security_key(key_id: str):
    """Xóa vĩnh viễn 1 API Key"""
    success = api_key_manager.delete_key(key_id)
    if not success:
        raise HTTPException(status_code=404, detail="API Key không tồn tại")
    return {"status": "ok", "message": "Đã xóa API Key thành công"}

@app.post("/api/security/keys/{key_id}/toggle")
def toggle_security_key(key_id: str):
    """Bật hoặc Vô hiệu hóa (Tắt) tạm thời 1 API Key"""
    res = api_key_manager.toggle_key(key_id)
    if not res:
        raise HTTPException(status_code=404, detail="API Key không tồn tại")
    return {"status": "ok", "key": res}

@app.get("/api/stats")
def get_stats():
    pool = load_sso_pool()
    history = load_history()
    success_count = sum(1 for h in history if h.get("status") == "success")
    fail_count = sum(1 for h in history if h.get("status") == "failed")
    durations = [h.get("duration", 0) for h in history if h.get("status") == "success"]
    avg_speed = round(sum(durations) / len(durations), 1) if durations else 0

    return {
        "total_accounts": len(pool),
        "active_tokens": len(pool),
        "total_requests": len(history),
        "success_images": success_count,
        "failed_requests": fail_count,
        "avg_duration_seconds": avg_speed,
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "online"
    }

@app.get("/api/request-logs")
def get_request_logs(status: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    """Lấy danh sách log các request (Client IP, Method, Path, Model, Status Code 200/404/500, Latency)"""
    logs = load_request_logs()
    if status and status != "all":
        if status == "2xx":
            logs = [l for l in logs if 200 <= l.get("status_code", 0) < 300]
        elif status == "404":
            logs = [l for l in logs if l.get("status_code") == 404]
        elif status == "4xx":
            logs = [l for l in logs if 400 <= l.get("status_code", 0) < 500]
        elif status == "5xx":
            logs = [l for l in logs if l.get("status_code") >= 500]
        elif status.isdigit():
            logs = [l for l in logs if l.get("status_code") == int(status)]

    if search:
        s = search.lower()
        logs = [l for l in logs if s in l.get("ip", "").lower() or s in l.get("path", "").lower() or s in l.get("user_agent", "").lower() or s in l.get("model", "").lower()]

    return {
        "total": len(logs),
        "logs": logs[:limit]
    }

@app.get("/api/request-stats")
def get_request_stats():
    """Thống kê tổng hợp: Số lượng 200 OK, 404 Not Found, 500 Error, Unique IPs"""
    logs = load_request_logs()
    total = len(logs)
    c_2xx = sum(1 for l in logs if 200 <= l.get("status_code", 0) < 300)
    c_404 = sum(1 for l in logs if l.get("status_code") == 404)
    c_4xx_other = sum(1 for l in logs if 400 <= l.get("status_code", 0) < 500 and l.get("status_code") != 404)
    c_5xx = sum(1 for l in logs if l.get("status_code") >= 500)
    
    unique_ips = list(set(l.get("ip") for l in logs if l.get("ip")))
    durations = [l.get("duration_ms", 0) for l in logs if l.get("duration_ms")]
    avg_latency = round(sum(durations) / len(durations), 1) if durations else 0

    return {
        "total_requests": total,
        "status_2xx": c_2xx,
        "status_404": c_404,
        "status_4xx_other": c_4xx_other,
        "status_5xx": c_5xx,
        "unique_ips_count": len(unique_ips),
        "unique_ips": unique_ips[:10],
        "avg_latency_ms": avg_latency
    }

@app.post("/api/request-logs/clear")
def clear_request_logs():
    """Xóa toàn bộ lịch sử log request"""
    with req_log_lock:
        with open(REQUEST_LOGS_JSON, "w", encoding="utf-8") as f:
            json.dump([], f)
    return {"status": "ok", "message": "Đã xóa toàn bộ log request thành công"}

@app.get("/api/history")
def get_history(limit: int = 50):
    history = load_history()
    return history[:limit]

@app.get("/api/pool")
def get_pool_data():
    """Lấy thống kê toàn bộ Pool và chi tiết Quota từng tài khoản"""
    return pool_manager.get_pool_summary()

@app.post("/api/pool/reset-all")
def reset_all_pool_quotas():
    """Reset lại toàn bộ quota của tất cả tài khoản về 100%"""
    pool_manager.reset_all_quotas()
    return {"status": "ok", "message": "Đã reset toàn bộ Quota tài khoản về ban đầu"}

@app.post("/api/pool/clean-dead")
def clean_dead_pool_tokens():
    """Dọn sạch các token chết/hết hạn ra khỏi Pool và file grok.txt"""
    return pool_manager.clean_dead_tokens()

@app.post("/api/pool/health-check")
async def trigger_pool_health_check():
    """Kích hoạt quét kiểm tra sống/chết toàn bộ tài khoản trong Pool"""
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, pool_manager.scan_all_tokens_health)
    return res

@app.post("/api/pool/keep-alive")
async def trigger_pool_keep_alive():
    """Kích hoạt nuôi và gia hạn Session cho các tài khoản đang Healthy"""
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, pool_manager.keep_alive_all_healthy)
    return res

@app.post("/api/pool/auto-relogin")
async def trigger_pool_auto_relogin():
    """Tự động đăng nhập lại các nick cũ có trong accounts.txt để lấy Session SSO mới"""
    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(None, pool_manager.auto_relogin_dead_accounts)
    return res

@app.post("/api/pool/sync")
def sync_pool_accounts():
    """Đồng bộ danh sách tài khoản mới từ file txt vào Pool"""
    pool_manager.sync_from_files()
    return {"status": "ok", "message": "Đã đồng bộ tài khoản thành công"}

@app.get("/api/accounts")
def get_accounts():
    pool_data = pool_manager.get_pool_summary()
    return {
        "total": pool_data["total_accounts"],
        "accounts": pool_data["accounts"]
    }

@app.post("/api/draw")
async def api_direct_draw(req: DirectDrawRequest, request: Request):
    """Endpoint vẽ ảnh đơn giản"""
    request.state.model = req.model or "grok-imagine-image-2.0"
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, do_generate_image, req.prompt)
        if not res:
            raise HTTPException(status_code=500, detail="Không thể tạo ảnh từ Grok. Vui lòng thử lại.")
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/images/generations")
async def openai_image_generations(req: ImageGenRequest, request: Request):
    """Endpoint tạo ảnh tương thích 100% chuẩn OpenAI DALL-E"""
    request.state.model = req.model or "grok-imagine-image"
    verify_auth_and_rate_limit(request)
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, do_generate_image, req.prompt)
        if not res:
            raise HTTPException(status_code=500, detail="Grok image generation failed")
        return {
            "created": int(time.time()),
            "data": [
                {
                    "url": res["url"],
                    "revised_prompt": req.prompt
                }
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/chat/completions")
async def openai_chat_completions(req: ChatCompletionRequest, request: Request):
    """Endpoint chat tương thích chuẩn OpenAI Chat (cho model grok-imagine-image)"""
    request.state.model = req.model or "grok-3"
    verify_auth_and_rate_limit(request)
    user_prompt = ""
    for m in reversed(req.messages):
        if m.role == "user":
            user_prompt = m.content
            break
    if not user_prompt:
        raise HTTPException(status_code=400, detail="No user message found")

    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, do_generate_image, user_prompt)
        if not res or not res.get("url"):
            reply_text = "Xin lỗi, đã xảy ra lỗi khi tạo ảnh từ Grok."
        else:
            reply_text = f"![Generated Image]({res['url']})\n\n[Xem ảnh gốc chất lượng cao]({res['url']})"

        return {
            "id": f"chatcmpl_{int(time.time()*1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model or "grok-3",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(user_prompt.split()),
                "completion_tokens": len(reply_text.split()),
                "total_tokens": len(user_prompt.split()) + len(reply_text.split())
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Auto-Reg Background Trigger ──
def _run_reg_task(count: int):
    import subprocess
    cmd = f'"{sys.executable}" grok_free.py --count {count} --email-provider mailtm --direct'
    subprocess.run(cmd, shell=True, cwd=SCRIPT_DIR)

@app.post("/api/reg")
def trigger_reg(background_tasks: BackgroundTasks, count: int = 3):
    """Bấm nút trên Dashboard để tự động reg thêm nick trong background"""
    background_tasks.add_task(_run_reg_task, count)
    return {"status": "ok", "message": f"Đang tiến hành tạo thêm {count} nick trong nền..."}

# ── Serve Dashboard UI ──
@app.get("/")
def serve_dashboard():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Grok Dashboard Backend Running.</h1>")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🚀 GROK IMAGINE DASHBOARD & API GATEWAY")
    print("📡 Local Web UI:    http://127.0.0.1:8000")
    print("🔌 OpenAI Image API: http://127.0.0.1:8000/v1/images/generations")
    print("💬 OpenAI Chat API:  http://127.0.0.1:8000/v1/chat/completions")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)
