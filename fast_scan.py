"""
fast_scan.py — Quét và lọc proxy tốc độ cao (Fast Proxy Scanner)
─────────────────────────────────────────────────────────────
- Đọc danh sách proxy từ proxies.txt (hoặc nhập đường dẫn)
- Kiểm tra kết nối đa luồng (50 - 100 luồng đồng thời) tới Cloudflare / accounts.x.ai
- Tự động lọc ra các proxy sống, đo độ trễ (ping ms)
- Lưu danh sách proxy tốt nhất vào good_proxies.txt
"""
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import common  # noqa: F401


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXIES_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")
GOOD_PROXIES_FILE = os.path.join(SCRIPT_DIR, "good_proxies.txt")

TEST_URL = "https://accounts.x.ai"
TIMEOUT = 6

def test_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str or proxy_str.startswith("#"):
        return None
        
    formatted_proxy = proxy_str
    if not formatted_proxy.startswith("http://") and not formatted_proxy.startswith("https://") and not formatted_proxy.startswith("socks5://"):
        # Format ip:port:user:pass -> http://user:pass@ip:port
        parts = formatted_proxy.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            formatted_proxy = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            formatted_proxy = f"http://{formatted_proxy}"

    proxies = {
        "http": formatted_proxy,
        "https": formatted_proxy
    }
    
    start_t = time.time()
    try:
        r = requests.get(
            TEST_URL,
            proxies=proxies,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        latency = int((time.time() - start_t) * 1000)
        if r.status_code in [200, 301, 302, 403, 404]: # Kết nối thành công tới máy chủ
            return (proxy_str, latency)
    except Exception:
        pass
    return None

def scan_proxies(input_file=PROXIES_FILE, max_workers=50):
    if not os.path.exists(input_file):
        print(f"[!] Không tìm thấy file {input_file}. Tạo file mẫu...")
        with open(input_file, "w", encoding="utf-8") as f:
            f.write("# Dán danh sách proxy vào đây (ip:port hoặc ip:port:user:pass)\n")
        return

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    total = len(lines)
    print(f"[*] Bắt đầu quét {total} proxy với {max_workers} luồng đồng thời...")
    print(f"[*] Mục tiêu test: {TEST_URL} (Timeout: {TIMEOUT}s)")
    print("-" * 60)

    good_proxies = []
    done_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_proxy, p): p for p in lines}
        for future in as_completed(futures):
            done_count += 1
            res = future.result()
            if res:
                p_str, latency = res
                good_proxies.append((p_str, latency))
                print(f"[{done_count}/{total}] ✅ HOẠT ĐỘNG: {p_str} ({latency}ms)")
            else:
                if done_count % 10 == 0 or done_count == total:
                    print(f"[{done_count}/{total}] Đang quét...", end="\r", flush=True)

    print("\n" + "=" * 60)
    print(f"🎉 Hoàn thành quét! Tìm thấy {len(good_proxies)}/{total} proxy hoạt động tốt.")

    # Sắp xếp theo ping nhanh nhất
    good_proxies.sort(key=lambda x: x[1])

    with open(GOOD_PROXIES_FILE, "w", encoding="utf-8") as f:
        for p_str, lat in good_proxies:
            f.write(f"{p_str}\n")

    print(f"💾 Đã lưu danh sách proxy tốt vào: {GOOD_PROXIES_FILE}")

if __name__ == "__main__":
    workers = 50
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except Exception:
            pass
    scan_proxies(max_workers=workers)
