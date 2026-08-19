"""
Fast Proxy Scanner & Purger for Grok Registration
────────────────────────────────────────────────
Quét đa luồng (100 threads) toàn bộ proxies.txt:
1. Tự động test 3 giao thức: HTTP → SOCKS5 → SOCKS4
2. Lưu Proxy Sống (kèm đúng giao thức) vào good_proxies.txt
3. Xóa sạch proxies.txt sau khi quét xong (chờ dán IP mới)
"""
import certifi, os, sys, time, concurrent.futures

_safe_ca_path = r"C:\Users\Admin\cacert.pem"
try:
    if not os.path.exists(_safe_ca_path):
        with open(certifi.where(), "rb") as _f1, open(_safe_ca_path, "wb") as _f2:
            _f2.write(_f1.read())
    certifi.where = lambda: _safe_ca_path
    os.environ["SSL_CERT_FILE"] = _safe_ca_path
    os.environ["REQUESTS_CA_BUNDLE"] = _safe_ca_path
    os.environ["CURL_CA_BUNDLE"] = _safe_ca_path
except Exception:
    pass

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from curl_cffi import requests as cf_req

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXIES_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")
GOOD_FILE = os.path.join(SCRIPT_DIR, "good_proxies.txt")
TEST_URL = "https://accounts.x.ai/sign-up?redirect=grok-com"

def _extract_ip_port(proxy_str):
    """Tách IP:PORT thuần từ bất kỳ định dạng nào (http://ip:port, socks5://ip:port, ip:port)"""
    s = proxy_str.strip()
    for prefix in ("http://", "https://", "socks5://", "socks4://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip("/").strip()

def test_proxy(proxy_str):
    """Test 1 proxy theo thứ tự: HTTP → SOCKS5 → SOCKS4. Trả về 'protocol://ip:port' hoặc None."""
    ip_port = _extract_ip_port(proxy_str)
    if not ip_port or ":" not in ip_port:
        return None

    # Nếu proxy đã có giao thức rõ ràng, chỉ test giao thức đó
    raw = proxy_str.strip()
    if raw.startswith("socks5://"):
        protocols = [("socks5", f"socks5://{ip_port}")]
    elif raw.startswith("socks4://"):
        protocols = [("socks4", f"socks4://{ip_port}")]
    elif raw.startswith("http://") or raw.startswith("https://"):
        protocols = [("http", f"http://{ip_port}")]
    else:
        # Không rõ giao thức → thử cả 3 theo thứ tự
        protocols = [
            ("http",   f"http://{ip_port}"),
            ("socks5", f"socks5://{ip_port}"),
            ("socks4", f"socks4://{ip_port}"),
        ]

    for proto_name, px_url in protocols:
        try:
            r = cf_req.get(TEST_URL, proxies={"http": px_url, "https": px_url},
                           timeout=5, impersonate="chrome120")
            if r.status_code == 200 and len(r.text) > 1000:
                return px_url  # Trả về kèm giao thức đúng
        except Exception:
            pass
    return None

def main():
    if not os.path.exists(PROXIES_FILE):
        print("[!] proxies.txt không tồn tại")
        return

    raw_proxies = [l.strip() for l in open(PROXIES_FILE, encoding="utf-8", errors="ignore") if l.strip()]
    total = len(raw_proxies)
    if total == 0:
        print("[!] proxies.txt trống, không có gì để quét.")
        return

    print(f"🚀 Bắt đầu quét 100 luồng siêu tốc {total} Proxy (tự động phân loại HTTP/SOCKS5/SOCKS4)...")

    working = []
    stats = {"http": 0, "socks5": 0, "socks4": 0}
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(test_proxy, p): p for p in raw_proxies}
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            res = future.result()
            if res:
                working.append(res)
                # Phân loại theo giao thức
                if res.startswith("socks5://"):
                    stats["socks5"] += 1
                    tag = "🟣 SOCKS5"
                elif res.startswith("socks4://"):
                    stats["socks4"] += 1
                    tag = "🟠 SOCKS4"
                else:
                    stats["http"] += 1
                    tag = "🟢 HTTP"
                print(f"  ⭐ [{len(working)}] {tag} Proxy sống: {res}")
            if completed % 500 == 0 or completed == total:
                elapsed = time.time() - t0
                print(f"  📊 Tiến độ: {completed}/{total} ({completed*100//total}%) | "
                      f"Sống: {len(working)} (HTTP:{stats['http']} SOCKS5:{stats['socks5']} SOCKS4:{stats['socks4']}) | "
                      f"Thời gian: {elapsed:.1f}s")

    print("=" * 60)
    print(f"✅ Quét xong! Tìm được {len(working)}/{total} Proxy sống 100%")
    print(f"   🟢 HTTP: {stats['http']}  |  🟣 SOCKS5: {stats['socks5']}  |  🟠 SOCKS4: {stats['socks4']}")

    if working:
        # Đọc danh sách good_proxies.txt hiện có để merge (không ghi đè)
        existing = set()
        if os.path.exists(GOOD_FILE):
            with open(GOOD_FILE, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    l = line.strip()
                    if l:
                        existing.add(_extract_ip_port(l))

        new_count = 0
        with open(GOOD_FILE, "a", encoding="utf-8") as f:
            for w in working:
                ip_port = _extract_ip_port(w)
                if ip_port not in existing:
                    f.write(w + "\n")
                    existing.add(ip_port)
                    new_count += 1

        # Xóa sạch proxies.txt, chờ dán IP mới
        with open(PROXIES_FILE, "w", encoding="utf-8") as f:
            f.write("")

        total_good = len(existing)
        print(f"💾 Đã thêm {new_count} Proxy mới vào {GOOD_FILE} (tổng cộng: {total_good})")
        print(f"🗑️ Đã xóa sạch {PROXIES_FILE} (sẵn sàng dán IP mới)")
    else:
        print("⚠️ Không tìm thấy Proxy nào sống trong proxies.txt.")

if __name__ == "__main__":
    main()
