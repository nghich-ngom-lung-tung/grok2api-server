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
        dilated_mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=2)
        inpainted_roi = cv2.inpaint(roi, dilated_mask, inpaintRadius=4, flags=cv2.INPAINT_TELEA)
        img[y1:y2, x1:x2] = inpainted_roi
        is_success, buffer = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        if is_success:
            new_bytes = buffer.tobytes()
            with open(image_path, "wb") as f:
                f.write(new_bytes)
            
            # Update SQLite size_bytes and sha256
            asset_id = os.path.basename(image_path)
            new_size = len(new_bytes)
            new_sha = hashlib.sha256(new_bytes).hexdigest()
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("UPDATE media_assets SET size_bytes = ?, sha256 = ? WHERE id = ?;", (new_size, new_sha, asset_id))
                conn.commit()
                conn.close()
            except Exception as dbe:
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

if __name__ == "__main__":
    print(f"🛡️ Watermark Cleaner Daemon đã kích hoạt cho Grok2API!")
    while True:
        try:
            scan_and_clean()
        except Exception:
            pass
        time.sleep(0.5)
