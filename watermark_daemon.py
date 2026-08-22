import sys, os, time, glob, hashlib, sqlite3
sys.stdout.reconfigure(encoding='utf-8')
import cv2
import numpy as np

MEDIA_DIR = os.path.join(os.getcwd(), "grok2api_repo", "data", "media", "images")
DB_PATH = os.path.join(os.getcwd(), "grok2api_repo", "data", "backend.db")
PROCESSED_LOG = os.path.join(os.getcwd(), "grok2api_repo", "data", ".processed_watermarks.txt")

def remove_grok_watermark(image_path: str) -> bool:
    try:
        with open(image_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if img is None:
            return False
            
        h, w = img.shape[:2]
        crop_h = int(h * 0.12)
        crop_w = int(w * 0.25)
        y1, y2 = h - crop_h, h
        x1, x2 = w - crop_w, w
        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
        _, mask = cv2.threshold(tophat, 40, 255, cv2.THRESH_BINARY)
        dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        dilated_mask = cv2.dilate(mask, dilate_kernel, iterations=2)
        # Inpaint xóa watermark
        inpainted_roi = cv2.inpaint(roi, dilated_mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)
        img[y1:y2, x1:x2] = inpainted_roi

        # 💎 TỰ ĐỘNG UPSCALE LÊN CHUẨN 4K (4x Lanczos Super-Res)
        # Giúp mọi ảnh trả về qua endpoint API đạt chuẩn 4K / in ấn POD
        target_w = w * 4
        target_h = h * 4
        img_4k = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

        is_success, buffer = cv2.imencode(".jpg", img_4k, [int(cv2.IMWRITE_JPEG_QUALITY), 98])
        if is_success:
            new_bytes = buffer.tobytes()
            with open(image_path, "wb") as f:
                f.write(new_bytes)
            
            # Update SQLite size_bytes and sha256
            asset_id = os.path.splitext(os.path.basename(image_path))[0]
            new_size = len(new_bytes)
            new_sha = hashlib.sha256(new_bytes).hexdigest()
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("UPDATE media_assets SET size_bytes = ?, sha256 = ? WHERE id = ?;", (new_size, new_sha, asset_id))
                conn.commit()
                conn.close()
            except Exception:
                pass
                
            return True
    except Exception as e:
        print(f"[!] Lỗi xóa watermark trên {image_path}: {e}")
    return False

def get_processed_set():
    if not os.path.exists(PROCESSED_LOG):
        return set()
    with open(PROCESSED_LOG, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def mark_processed(filepath):
    with open(PROCESSED_LOG, "a", encoding="utf-8") as f:
        f.write(filepath + "\n")

def scan_and_clean():
    if not os.path.exists(MEDIA_DIR):
        return
    processed = get_processed_set()
    for root, _, files in os.walk(MEDIA_DIR):
        for file in files:
            full_path = os.path.abspath(os.path.join(root, file))
            if full_path in processed:
                continue
            try:
                size1 = os.path.getsize(full_path)
                if size1 == 0:
                    continue
                time.sleep(0.05)
                size2 = os.path.getsize(full_path)
                if size1 == size2:
                    if remove_grok_watermark(full_path):
                        print(f"✨ [AI Inpainting] Đã tự động xóa sạch 100% Watermark & đồng bộ size: {os.path.basename(full_path)}")
                    mark_processed(full_path)
            except Exception:
                pass

# ── Tự động dọn dẹp tài khoản hết hạn (chạy mỗi 6 giờ) ─────────────
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60  # 6 giờ

def auto_cleanup_expired_accounts():
    """Gọi Admin API để quét và xóa tài khoản reauthRequired/disabled."""
    try:
        from common import get_admin_token, get_base_url
        import requests as _req

        base = get_base_url()
        token = get_admin_token(base)
        if not token:
            return

        headers = {"Authorization": f"Bearer {token}"}

        # Làm mới trạng thái
        _req.post(f"{base}/api/admin/v1/accounts/web/refresh-quotas", headers=headers, timeout=30)
        time.sleep(2)

        # Lấy danh sách
        r = _req.get(f"{base}/api/admin/v1/accounts?pageSize=500", headers=headers, timeout=20)
        if r.status_code != 200:
            return

        accounts = r.json().get("data", {}).get("items", [])
        expired = [a for a in accounts if a.get("authStatus") in ("reauthRequired", "disabled", "invalid")]

        if not expired:
            active_count = len([a for a in accounts if a.get("authStatus") not in ("reauthRequired", "disabled", "invalid")])
            print(f"🔄 [Auto-Cleanup] Tất cả {active_count} tài khoản đều khỏe mạnh — không cần dọn dẹp.")
            return

        deleted = 0
        for acc in expired:
            try:
                dr = _req.delete(f"{base}/api/admin/v1/accounts/{acc['id']}", headers=headers, timeout=10)
                if dr.status_code in (200, 204):
                    deleted += 1
            except Exception:
                pass

        print(f"🧹 [Auto-Cleanup] Đã tự động xóa {deleted}/{len(expired)} tài khoản hết hạn!")

    except Exception as e:
        print(f"[!] Auto-cleanup lỗi: {e}")


if __name__ == "__main__":
    print(f"🛡️ Watermark Cleaner Daemon đã kích hoạt cho Grok2API!")
    print(f"🔄 Auto-Cleanup tài khoản hết hạn: mỗi {CLEANUP_INTERVAL_SECONDS // 3600} giờ")

    last_cleanup = 0

    while True:
        try:
            scan_and_clean()
        except Exception:
            pass

        # Kiểm tra xem đã đến lúc dọn dẹp tài khoản chưa
        now = time.time()
        if now - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
            auto_cleanup_expired_accounts()
            last_cleanup = now

        time.sleep(0.5)

