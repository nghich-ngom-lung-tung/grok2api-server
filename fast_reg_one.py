import sys, os, time, re
sys.stdout.reconfigure(encoding='utf-8')
from DrissionPage import ChromiumPage, ChromiumOptions
import requests, json

print("="*60)
print("🚀 ĐĂNG KÝ 1 TÀI KHOẢN GROK MỚI TINH TRỰC TIẾP")
print("="*60)

from email_service import EmailService

email_svc = EmailService(provider="mailtm")
token_like, email = email_svc.create_email()
print(f"[+] Email tạo được: {email}")

co = ChromiumOptions()
co.set_argument('--no-sandbox')
co.set_argument('--disable-gpu')

page = ChromiumPage(co)
sso_cookie = None

try:
    print("[1] Mở trang đăng ký https://grok.com...")
    page.get("https://grok.com", timeout=30)
    time.sleep(3)
    
    # Click Sign In / Sign Up
    btn_sign = page.ele('text:Sign in') or page.ele('text:Sign In') or page.ele('tag:button@@text():Sign in')
    if btn_sign:
        btn_sign.click()
        time.sleep(2)
        
    # Input email
    inp_email = page.ele('@type=email') or page.ele('@name=email') or page.ele('tag:input')
    if inp_email:
        print(f"[2] Điền email: {email}")
        inp_email.input(email)
        time.sleep(1)
        btn_cont = page.ele('text:Continue') or page.ele('text:Tiếp tục') or page.ele('tag:button@@type=submit')
        if btn_cont:
            btn_cont.click()
            time.sleep(3)
            
    # Chờ mã xác nhận từ email
    print("[3] Đang chờ mã OTP từ Grok gửi về email...")
    otp_code = None
    for i in range(25):
        time.sleep(2)
        msg_body = email_svc.fetch_first_email(token_like)
        if msg_body:
            print(f"Nhận được email:\n{msg_body[:200]}...")
            match = re.search(r'\b\d{6}\b', msg_body)
            if match:
                otp_code = match.group(0)
                print(f"[✓] Đã nhận được mã OTP: {otp_code}")
                break
            
    if otp_code:
        inp_otp = page.ele('@type=text') or page.ele('tag:input')
        if inp_otp:
            inp_otp.input(otp_code)
            time.sleep(4)
            
        for c in page.cookies():
            if c.get("name") == "sso":
                sso_cookie = c.get("value")
                break
finally:
    page.quit()

print(f"\n[✓] KẾT QUẢ SSO MỚI TINH: {sso_cookie}")

if sso_cookie:
    with open("keys/accounts.txt", "a", encoding="utf-8") as f:
        f.write(f"{email}----Password123!----{sso_cookie}\n")
    print("[✓] Đã lưu vào keys/accounts.txt!")
