import sys, os, time, sqlite3, requests
sys.stdout.reconfigure(encoding='utf-8')
from DrissionPage import ChromiumPage, ChromiumOptions

print("="*60)
print("🚀 VƯỢT CLOUDFLARE BẰNG DRISSIONPAGE & LẤY CF_CLEARANCE")
print("="*60)

co = ChromiumOptions()
co.set_argument('--no-sandbox')
co.set_argument('--disable-gpu')
co.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

page = ChromiumPage(co)
cf_clearance = None

try:
    print("[1] Mở trang https://grok.com...")
    page.get("https://grok.com", timeout=30)
    
    # Chờ Turnstile xuất hiện và click nếu có
    for sec in range(12):
        time.sleep(1)
        # Check if turnstile iframe exists and click
        try:
            iframe = page.get_frame('@src^https://challenges.cloudflare.com')
            if iframe:
                box = iframe.ele('tag:input') or iframe.ele('@type=checkbox') or iframe.ele('.ctp-checkbox-label')
                if box:
                    print(f"[*] Phát hiện Cloudflare checkbox, đang tự động click...")
                    box.click()
        except Exception:
            pass
            
        for c in page.cookies():
            if c.get("name") == "cf_clearance":
                cf_clearance = c.get("value")
                break
        if cf_clearance:
            print(f"[✓] Đã bắt được cf_clearance sau {sec+1}s!")
            break
finally:
    page.quit()

print(f"Cookie cf_clearance: {cf_clearance}")

if cf_clearance:
    resp = requests.post("http://127.0.0.1:8080/api/admin/v1/auth/login", json={"username": "admin", "password": "adminpassword123"})
    access_token = resp.json()['data']['tokens']['accessToken']
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    acc_res = requests.get("http://127.0.0.1:8080/api/admin/v1/accounts", headers=headers)
    items = acc_res.json().get("data", {}).get("items", [])
    
    for acc in items:
        aid = acc.get("id")
        patch_res = requests.put(f"http://127.0.0.1:8080/api/admin/v1/accounts/{aid}", headers=headers, json={
            "cloudflareCookie": f"cf_clearance={cf_clearance}",
            "enabled": True
        })
        print(f"[+] Cập nhật tài khoản {aid}: {patch_res.status_code}")
    print("[✓] Nạp hoàn tất vào Grok2API!")
