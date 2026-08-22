"""
generate_video_browser.py — Tạo Video/Clip tự động từ Grok qua Trình duyệt
──────────────────────────────────────────────────────────────────────────
Sử dụng DrissionPage điều khiển trình duyệt thật để vượt Cloudflare Turnstile:
1. Nạp Cookie SSO của tài khoản vào grok.com
2. Nhập prompt tạo ảnh/video
3. Kích hoạt tính năng Animate Video
4. Chờ video render xong và tự động tải file .mp4 về máy!

Cách dùng:
    uv run python generate_video_browser.py "a cute puppy running in green park"
"""
import sys
import os
import time
import requests
import argparse
import common  # noqa: F401
from DrissionPage import ChromiumPage, ChromiumOptions

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(SCRIPT_DIR, "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)


def get_active_account():
    """Lấy tài khoản đầu tiên trong keys/accounts.txt."""
    acc_file = os.path.join(SCRIPT_DIR, "keys", "accounts.txt")
    with open(acc_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) >= 3:
                return {"email": parts[0], "password": parts[1], "sso": parts[2]}
    return None


def generate_video(prompt, output_filename=None):
    account = get_active_account()
    if not account:
        print("[❌] Không tìm thấy tài khoản trong keys/accounts.txt")
        return None

    if not output_filename:
        safe_name = "".join(c if c.isalnum() else "_" for c in prompt[:30])
        output_filename = f"clip_{int(time.time())}_{safe_name}.mp4"

    output_path = os.path.join(VIDEOS_DIR, output_filename)

    print("=" * 65)
    print(f"🎬 BẮT ĐẦU TẠO CLIP TỰ ĐỘNG BẰNG TRÌNH DUYỆT")
    print(f"👤 Tài khoản: {account['email']}")
    print(f"📝 Prompt: \"{prompt}\"")
    print(f"💾 File đầu ra: {output_path}")
    print("=" * 65)

    co = ChromiumOptions()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-gpu')
    co.auto_port()

    temp_dir = os.path.join(SCRIPT_DIR, "temp_chrome", "video_gen")
    os.makedirs(temp_dir, exist_ok=True)
    co.set_argument(f"--user-data-dir={temp_dir}")

    page = ChromiumPage(co)
    video_url = None

    try:
        print("[1/5] 🌐 Đang nạp Cookie SSO vào grok.com...")
        page.get("https://grok.com", timeout=30)
        time.sleep(1)
        page.set.cookies({"name": "sso", "value": account["sso"], "domain": ".grok.com", "path": "/"})
        page.set.cookies({"name": "sso-rw", "value": account["sso"], "domain": ".grok.com", "path": "/"})

        print("[2/5] 🎨 Đang mở trang Imagine...")
        page.get("https://grok.com/imagine", timeout=30)
        time.sleep(3)

        # Xóa banner nếu có
        page.run_js('''
        var b1 = document.getElementById("onetrust-consent-sdk"); if(b1) b1.remove();
        var b2 = document.getElementById("onetrust-banner-sdk"); if(b2) b2.remove();
        ''')

        # Tìm ô nhập prompt
        textarea = page.ele("tag:textarea") or page.ele("@placeholder*Imagine") or page.ele("@placeholder*Ask") or page.ele(".ProseMirror")
        if not textarea:
            print("[❌] Không tìm thấy ô nhập prompt trên grok.com")
            return None

        print(f"[3/5] ✍️ Đang nhập prompt: \"{prompt}\"...")
        textarea.input(prompt)
        time.sleep(1)

        # Bấm gửi
        btn_send = page.ele("@aria-label*Send") or page.ele("tag:button@@type=submit")
        if btn_send:
            btn_send.click()
        else:
            textarea.input('\n')

        print("[4/5] ⏳ Đang chờ ảnh tạo và kích hoạt nút Video (Animate)...")
        time.sleep(15)

        # Chụp màn hình để debug
        snap = os.path.join(SCRIPT_DIR, "video_step1.png")
        page.get_screenshot(path=snap)

        # Tìm nút Animate
        btn_animate = (
            page.ele("text:Animate")
            or page.ele("text:Tạo video")
            or page.ele("@aria-label*video")
            or page.ele("@aria-label*Animate")
            or page.ele("tag:button@@text():Animate")
        )

        if not btn_animate:
            # Thử click vào ảnh đầu tiên để mở thanh công cụ
            imgs = page.eles("tag:img")
            for img in imgs:
                if "assets.grok.com" in (img.attr("src") or ""):
                    img.click()
                    time.sleep(2)
                    btn_animate = page.ele("text:Animate") or page.ele("@aria-label*Animate")
                    if btn_animate:
                        break

        if btn_animate:
            print("[✓] Đã tìm thấy nút Animate! Đang bấm tạo Video...")
            btn_animate.click()
            print("[5/5] 🎬 Đang chờ xAI render Video (khoảng 30 - 60s)...")

            for sec in range(90):
                time.sleep(2)
                # Kiểm tra thẻ video trên trang
                video_ele = page.ele("tag:video")
                if video_ele:
                    src = video_ele.attr("src")
                    if src and "http" in src:
                        video_url = src
                        break

                # Kiểm tra thẻ source trong video
                src_ele = page.ele("tag:source")
                if src_ele:
                    src = src_ele.attr("src")
                    if src and "http" in src:
                        video_url = src
                        break

        else:
            print("[-] Chưa kích hoạt được nút Animate trên UI")

    except Exception as e:
        print(f"[!] Lỗi tiến trình: {e}")
    finally:
        page.quit()

    if video_url:
        print(f"\n🎉 TẠO VIDEO THÀNH CÔNG! Link video: {video_url}")
        print(f"📥 Đang tải file video về: {output_path}...")
        try:
            r = requests.get(video_url, stream=True, timeout=60)
            with open(output_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✨ [✓] Đã lưu file video thành công: {output_path}")
            return output_path
        except Exception as e:
            print(f"[!] Lỗi tải file: {e}")
            return video_url
    else:
        print("\n[-] Chưa lấy được link video .mp4")
        return None


if __name__ == "__main__":
    prompt_arg = "a cute neon cyberpunk cat walking on tokyo street at night, 4k video"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        prompt_arg = sys.argv[1]
    generate_video(prompt_arg)
