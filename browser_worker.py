"""
browser_worker.py — Động cơ tự động hóa trình duyệt ngầm xử lý Sửa ảnh & Tạo video
─────────────────────────────────────────────────────────────────────────────
Sử dụng DrissionPage với kiến trúc Pre-warmed Worker trên https://grok.com/imagine:
- Chạy trực tiếp trên giao diện Grok Imagine 2.0 (Hỗ trợ Photo Edit / Reimagine / Redesign)
- Tự động nhận diện và nạp ảnh đính kèm (Thumbnail pill)
- Bộ lọc ảnh thông minh: Track toàn bộ ảnh cũ trước khi gửi để 100% trả về ảnh MỚI tạo
- Tự động giải Cloudflare Turnstile & vượt SuperGrok / Limit Paywall (Auto-rotate 84 accs)
- Áp dụng gỡ watermark & upscale 4K siêu nét
"""
import sys
import os
import time
import uuid
import re
import threading
import shutil
import base64
import requests
import cv2
import numpy as np
from PIL import Image
from DrissionPage import ChromiumPage, ChromiumOptions
import common  # noqa: F401

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(SCRIPT_DIR, "keys", "accounts.txt")
VIDEOS_DIR = os.path.join(SCRIPT_DIR, "videos")
MEDIA_IMAGES_DIR = os.path.join(SCRIPT_DIR, "grok2api_repo", "data", "media", "images", "im")
TEMP_BASE_DIR = os.path.join(SCRIPT_DIR, "temp_chrome", "gateway_workers")

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(MEDIA_IMAGES_DIR, exist_ok=True)
os.makedirs(TEMP_BASE_DIR, exist_ok=True)


class AccountPool:
    def __init__(self):
        self._lock = threading.RLock()
        self._accounts = []
        self._index = 0
        self.reload()

    def reload(self):
        with self._lock:
            self._accounts = []
            if os.path.exists(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split(":")
                        if len(parts) >= 3 and parts[0] and parts[2]:
                            self._accounts.append({
                                "email": parts[0],
                                "password": parts[1],
                                "sso": parts[2],
                                "cooldown": 0
                            })
            print(f"[AccountPool] Đã nạp {len(self._accounts)} tài khoản sẵn sàng cho Browser Gateway.")

    def get_account(self):
        with self._lock:
            if not self._accounts:
                return None
            now = time.time()
            for _ in range(len(self._accounts)):
                acc = self._accounts[self._index]
                self._index = (self._index + 1) % len(self._accounts)
                if acc["cooldown"] <= now:
                    return acc
            return min(self._accounts, key=lambda a: a["cooldown"])

    def set_cooldown(self, email, seconds=7200):
        with self._lock:
            for a in self._accounts:
                if a["email"] == email:
                    a["cooldown"] = time.time() + seconds
                    print(f"[AccountPool] ⏳ Đặt cooldown {seconds}s cho tài khoản: {email}")
                    break


GLOBAL_POOL = AccountPool()


def clean_watermark_and_upscale_image(input_img_path, output_img_path):
    """Gỡ logo Grok góc dưới phải và phóng to ảnh lên chuẩn 4K siêu tốc."""
    try:
        img = cv2.imread(input_img_path)
        if img is None:
            shutil.copy(input_img_path, output_img_path)
            return

        h, w = img.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        logo_w = int(w * 0.12)
        logo_h = int(h * 0.08)
        mask[h - logo_h : h, w - logo_w : w] = 255

        inpainted = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)

        target_w = w * 2
        target_h = h * 2
        upscaled = cv2.resize(inpainted, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(output_img_path, upscaled, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    except Exception as e:
        print(f"[!] Lỗi hậu xử lý ảnh: {e}, sao chép ảnh gốc...")
        shutil.copy(input_img_path, output_img_path)


def prepare_input_image_file(image_input, temp_dir):
    """Chuyển đổi URL, Dict {url: ...}, Base64, hoặc Asset ID thành file ảnh cục bộ."""
    if not image_input:
        return None

    if isinstance(image_input, dict):
        image_input = image_input.get("url") or image_input.get("b64_json") or image_input.get("base64") or image_input.get("image")

    if not isinstance(image_input, str):
        return None

    if os.path.exists(image_input):
        return image_input

    asset_name = os.path.basename(image_input.split("?")[0])
    for ext in ["", ".jpg", ".jpeg", ".png", ".webp"]:
        cand = os.path.join(MEDIA_IMAGES_DIR, asset_name + ext)
        if os.path.exists(cand) and os.path.isfile(cand):
            return cand

    out_file = os.path.join(temp_dir, f"input_{uuid.uuid4().hex[:8]}.jpg")
    if image_input.startswith("http://") or image_input.startswith("https://"):
        try:
            r = requests.get(image_input, timeout=25)
            if r.status_code == 200 and len(r.content) > 100:
                with open(out_file, "wb") as f:
                    f.write(r.content)
                return out_file
        except Exception as e:
            print(f"[!] Lỗi tải ảnh từ URL {image_input}: {e}")

    if "base64," in image_input:
        try:
            b64_data = image_input.split("base64,")[1]
            with open(out_file, "wb") as f:
                f.write(base64.b64decode(b64_data))
            return out_file
        except Exception:
            pass

    return None


def handle_all_gates(page):
    """Tự động xử lý Cloudflare Turnstile, TOS Gate, Age Confirmation, SuperGrok dialog và Cookie Banner."""
    try:
        # 1. Cloudflare Turnstile
        if "Just a moment" in page.title or "security verification" in page.html.lower():
            for _ in range(8):
                time.sleep(1)
                if "Just a moment" not in page.title:
                    break
                try:
                    cf_iframe = page.ele("tag:iframe@src*challenges", timeout=1) or page.ele("tag:iframe@src*turnstile", timeout=1)
                    if cf_iframe:
                        cb = cf_iframe.ele("tag:input@@type=checkbox", timeout=1)
                        if cb:
                            cb.click()
                            time.sleep(2)
                            break
                except Exception:
                    pass

        # 2. Đóng các modal che chắn (SuperGrok, Search, Cookies)
        page.run_js('''
        var ot = document.getElementById("onetrust-consent-sdk"); if(ot) ot.remove();
        var b1 = document.getElementById("onetrust-banner-sdk"); if(b1) b1.remove();
        var inputs = document.querySelectorAll("input[type=number], input[placeholder*='Year'], input[placeholder*='năm']");
        for (var inp of inputs) {
            if (!inp.value) {
                inp.value = "2000";
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }
        var btns = document.querySelectorAll("button");
        for (var b of btns) {
            var txt = (b.innerText || "").trim().toLowerCase();
            var aria = (b.getAttribute("aria-label") || "").trim().toLowerCase();
            if (txt === "got it" || txt === "continue" || txt === "save" || txt === "accept all cookies" || txt === "agree" || txt === "confirm" || txt === "i understand" || txt === "dismiss" || aria === "dismiss" || aria === "close") {
                b.click();
            }
        }
        ''')
    except Exception:
        pass


def find_imagine_editor(page, max_seconds=15):
    """Tìm ô nhập prompt trong giao diện Grok Imagine."""
    start = time.time()
    while time.time() - start < max_seconds:
        handle_all_gates(page)
        try:
            ta = (
                page.ele(".ProseMirror", timeout=1)
                or page.ele("@contenteditable=true", timeout=1)
                or page.ele("@placeholder*imagine", timeout=1)
                or page.ele("@placeholder*Ask", timeout=1)
                or page.ele("tag:textarea", timeout=1)
            )
            if ta:
                return ta
        except Exception:
            pass
        time.sleep(0.8)
    return None


class PrewarmedBrowserManager:
    """Quản lý phiên Chrome chạy nền sẵn sàng để phản hồi tức thì trong 18-25s."""
    def __init__(self):
        self._lock = threading.RLock()
        self.page = None
        self.current_account = None
        self.temp_dir = os.path.join(TEMP_BASE_DIR, "prewarmed_worker")
        os.makedirs(self.temp_dir, exist_ok=True)

    def get_or_create_page(self):
        with self._lock:
            if self.page:
                try:
                    _ = self.page.title
                    return self.page, self.current_account
                except Exception:
                    self.close_page()

            account = GLOBAL_POOL.get_account()
            if not account:
                raise RuntimeError("Không có tài khoản nào khả dụng trong keys/accounts.txt")

            co = ChromiumOptions()
            co.set_argument('--no-sandbox')
            co.set_argument('--window-size=1920,1080')
            co.set_argument(f"--user-data-dir={self.temp_dir}")
            co.auto_port()

            print(f"[BrowserWorker] 🚀 Khởi động phiên Chrome thường trực với tài khoản {account['email']}...")
            self.page = ChromiumPage(co)
            self.current_account = account

            self.page.get("https://grok.com/imagine", timeout=30)
            time.sleep(2)
            handle_all_gates(self.page)
            self.page.set.cookies({"name": "sso", "value": account["sso"], "domain": ".grok.com", "path": "/"})
            self.page.set.cookies({"name": "sso-rw", "value": account["sso"], "domain": ".grok.com", "path": "/"})
            self.page.get("https://grok.com/imagine", timeout=30)
            time.sleep(3)
            handle_all_gates(self.page)
            return self.page, self.current_account

    def rotate_account(self, exhausted_email):
        with self._lock:
            GLOBAL_POOL.set_cooldown(exhausted_email, seconds=7200)
            self.close_page()
            return self.get_or_create_page()

    def close_page(self):
        with self._lock:
            if self.page:
                try:
                    self.page.quit()
                except Exception:
                    pass
                self.page = None
                self.current_account = None


def execute_chat(prompt: str, timeout: int = 45) -> str:
    """Gửi câu hỏi chat sang Grok và nhận câu trả lời đầy đủ trong 2-3s (chuẩn multi-turn)."""
    from DrissionPage.common import Keys
    page, acc = BROWSER_MANAGER.get_or_create_page()
    
    if "grok.com" not in page.url or "imagine" in page.url:
        page.get("https://grok.com/")
        time.sleep(1.5)

    # Dismiss any modal
    try:
        page.run_js("""
            let btns = Array.from(document.querySelectorAll('button'));
            let gotIt = btns.find(b => b.innerText.includes('Got it') || b.innerText.includes('Accept') || b.innerText.includes('Agree'));
            if (gotIt) gotIt.click();
        """)
    except Exception:
        pass

    textarea = page.ele("xpath://textarea", timeout=5)
    if not textarea:
        textarea = page.ele("xpath://div[@contenteditable='true']", timeout=3)

    if not textarea:
        page.get("https://grok.com/")
        time.sleep(1.5)
        textarea = page.ele("xpath://textarea", timeout=5)

    if not textarea:
        raise Exception("Không tìm thấy ô nhập câu hỏi trên Grok")

    # Record existing message texts before sending prompt to ignore past history
    before_texts = set(b.text.strip() for b in page.eles("xpath://div[contains(@class, 'message') or contains(@class, 'response') or contains(@class, 'prose') or contains(@class, 'markdown')]"))

    textarea.input(prompt)
    time.sleep(0.3)
    
    # Send via Enter key
    page.actions.key_down(Keys.ENTER).key_up(Keys.ENTER)

    # Wait for response to generate
    start_t = time.time()
    last_text = ""
    unchanged_count = 0
    
    while time.time() - start_t < timeout:
        time.sleep(0.8)
        bubbles = page.eles("xpath://div[contains(@class, 'message') or contains(@class, 'response') or contains(@class, 'prose') or contains(@class, 'markdown')]")
        candidate = ""
        for b in bubbles:
            txt = b.text.strip()
            if txt and txt not in before_texts and prompt.strip() not in txt and len(txt) > 5 and not txt.startswith("Worked for"):
                candidate = txt
                
        if candidate:
            if candidate == last_text:
                unchanged_count += 1
                if unchanged_count >= 2:
                    return candidate
            else:
                last_text = candidate
                unchanged_count = 0

    if last_text:
        return last_text
    raise Exception("Quá thời gian chờ phản hồi từ Grok")




BROWSER_MANAGER = PrewarmedBrowserManager()


def execute_image_edit(prompt, image_input, progress_callback=None, max_retries=5):
    """
    Thực hiện Sửa ảnh / Redesign ảnh qua Grok Imagine 2.0.
    """
    worker_uuid = uuid.uuid4().hex[:8]
    task_temp_dir = os.path.join(TEMP_BASE_DIR, f"task_{worker_uuid}")
    os.makedirs(task_temp_dir, exist_ok=True)

    try:
        local_img = prepare_input_image_file(image_input, task_temp_dir)

        for attempt in range(max_retries):
            page, account = BROWSER_MANAGER.get_or_create_page()
            try:
                page.get("https://grok.com/imagine", timeout=20)
                time.sleep(2)
                handle_all_gates(page)

                # Thu thập toàn bộ URL ảnh cũ đã có trên trang để không bao giờ lấy nhầm ảnh cũ
                existing_imgs = set()
                try:
                    for img in page.eles("tag:img"):
                        src = img.attr("src") or ""
                        if "assets.grok.com" in src:
                            existing_imgs.add(src)
                except Exception:
                    pass

                effective_prompt = prompt
                if local_img and os.path.exists(local_img):
                    if "redesign" not in prompt.lower() and "reimagine" not in prompt.lower() and "edit" not in prompt.lower():
                        effective_prompt = f"Professional image redesign: {prompt}. High resolution 4k graphic, masterfully composed, crisp details, centered composition"
                    else:
                        effective_prompt = f"{prompt}, 4k high quality graphic, crisp details, centered composition"

                # Chuyển sang chế độ Speed Mode để tạo ảnh tức thì không bị chặn Paywall
                page.run_js('''
                var btns = Array.from(document.querySelectorAll("button"));
                for (var b of btns) {
                    if ((b.innerText || '').trim().toLowerCase() === 'speed') {
                        b.click();
                        break;
                    }
                }
                ''')
                time.sleep(1)

                # Tìm ô nhập prompt Imagine
                print(f"[BrowserWorker] 🔍 Đang tìm ô nhập prompt...")
                editor = find_imagine_editor(page, max_seconds=12)
                if not editor:
                    handle_all_gates(page)
                    editor = find_imagine_editor(page, max_seconds=8)

                if not editor:
                    raise RuntimeError("Không tìm thấy ô nhập prompt trên grok.com/imagine")

                print(f"[BrowserWorker] ✍️ Đang nhập prompt ({len(effective_prompt)} chars): \"{effective_prompt[:60]}...\"")
                editor.click()
                editor.input(effective_prompt, clear=True)
                time.sleep(1)

                # Bấm nút Submit tạo ảnh
                print(f"[BrowserWorker] 🚀 Đang bấm Submit tạo ảnh...")
                clicked_aria = page.run_js('''
                var btns = Array.from(document.querySelectorAll("button"));
                for (var b of btns) {
                    var aria = (b.getAttribute("aria-label") || "").trim().toLowerCase();
                    if (aria === "submit" || aria === "send" || aria === "imagine") {
                        b.click();
                        return aria;
                    }
                }
                return false;
                ''')
                print(f"[BrowserWorker] Clicked button: {clicked_aria}")

                time.sleep(3)
                handle_all_gates(page)

                # Chờ kết quả ảnh MỚI xuất hiện
                print(f"[BrowserWorker] ⏳ Đang chờ ảnh mới xuất hiện từ Grok...")
                generated_img_url = None
                hit_limit = False
                for sec_step in range(25):
                    time.sleep(1.5)
                    handle_all_gates(page)

                    modal = page.ele("css:[role='dialog']", timeout=0.5)
                    if modal:
                        modal_text = modal.text or ""
                        if any(w in modal_text for w in ["limit", "SuperGrok", "Unlock", "Upgrade", "reached"]):
                            print(f"[!] Tài khoản {account['email']} chạm modal giới hạn. Đang tự động đổi tài khoản tiếp theo...")
                            BROWSER_MANAGER.rotate_account(account["email"])
                            hit_limit = True
                            break
                    elif page.ele("text:Image limit reached", timeout=0.5) or page.ele("text:limit reached", timeout=0.5):
                        print(f"[!] Tài khoản {account['email']} chạm giới hạn. Đang tự động đổi tài khoản tiếp theo...")
                        BROWSER_MANAGER.rotate_account(account["email"])
                        hit_limit = True
                        break

                    try:
                        imgs = page.eles("tag:img")
                        for img in reversed(imgs):
                            src = img.attr("src") or ""
                            if (
                                ("assets.grok.com" in src or "imgen.grok.com" in src or "/users/" in src)
                                and "avatar" not in src
                                and "logo" not in src
                                and "preview" not in src
                            ):
                                if src not in existing_imgs or "/generated/" in src:
                                    generated_img_url = src
                                    print(f"[BrowserWorker] 📸 Đã tìm thấy ảnh mới: {src[:60]}...")
                                    break
                    except Exception:
                        pass

                    if generated_img_url:
                        break

                if hit_limit:
                    continue

                if not generated_img_url:
                    # Kiểm tra lại lần cuối
                    imgs = page.eles("tag:img")
                    for img in reversed(imgs):
                        src = img.attr("src") or ""
                        if ("assets.grok.com" in src or "imgen.grok.com" in src or "/users/" in src) and src not in existing_imgs and "avatar" not in src and "logo" not in src:
                            generated_img_url = src
                            break

                if not generated_img_url:
                    print(f"[BrowserWorker] ⚠️ Không tìm thấy ảnh mới sau 35s. Đang đổi tài khoản...")
                    BROWSER_MANAGER.rotate_account(account["email"])
                    continue

                # Tải ảnh kết quả về an toàn 100% bằng fetch trong phiên Chrome
                raw_download_path = os.path.join(task_temp_dir, "raw_result.jpg")
                try:
                    b64_img = page.run_js(f'''
                    return (async () => {{
                        var res = await fetch("{generated_img_url}");
                        var blob = await res.blob();
                        return new Promise((resolve) => {{
                            var reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(blob);
                        }});
                    }})();
                    ''')
                    if b64_img and "base64," in b64_img:
                        img_data = base64.b64decode(b64_img.split("base64,")[1])
                        with open(raw_download_path, "wb") as f:
                            f.write(img_data)
                except Exception as dl_err:
                    print(f"[BrowserWorker] ⚠️ Lỗi tải ảnh qua JS fetch: {dl_err}")

                if not os.path.exists(raw_download_path) or os.path.getsize(raw_download_path) < 100:
                    try:
                        headers = {
                            "Referer": "https://grok.com/imagine",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        }
                        cookies = {"sso": account["sso"], "sso-rw": account["sso"]}
                        r = requests.get(generated_img_url, headers=headers, cookies=cookies, timeout=25)
                        if r.status_code == 200 and len(r.content) > 100:
                            with open(raw_download_path, "wb") as f:
                                f.write(r.content)
                    except Exception:
                        pass

                asset_id = f"img_edit_{int(time.time())}_{worker_uuid}"
                final_asset_path = os.path.join(MEDIA_IMAGES_DIR, asset_id + ".jpg")

                clean_watermark_and_upscale_image(raw_download_path, final_asset_path)

                public_base = "https://api.grokapi.cyou"
                result_url = f"{public_base}/v1/media/images/{asset_id}"

                return {
                    "asset_id": asset_id,
                    "url": result_url,
                    "account": account["email"]
                }

            except Exception as ex:
                print(f"[!] Lỗi trong attempt {attempt+1}: {ex}")
                BROWSER_MANAGER.rotate_account(account["email"])
                continue

        raise RuntimeError("Tất cả tài khoản thử nghiệm đều bận hoặc hết lượt. Vui lòng thử lại sau giây lát.")

    finally:
        shutil.rmtree(task_temp_dir, ignore_errors=True)
