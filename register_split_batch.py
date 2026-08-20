import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

print("="*60)
print("🚀 BẮT ĐẦU ĐĂNG KÝ 25 TÀI KHOẢN GROK CHIA ĐỀU 2 BÊN EMAIL")
print("="*60)

print("\n[BATCH 1/2] 📬 Đang tạo 13 tài khoản qua MAIL.TM (Có Proxy)...")
subprocess.run(["uv", "run", "python", "auto_batch_register_and_sync.py", "13", "--proxy", "--email-provider", "mailtm"])

print("\n" + "="*60)
print("[BATCH 2/2] 📬 Đang tạo 12 tài khoản qua TEMPMAIL.LOL (Có Proxy)...")
print("="*60)
subprocess.run(["uv", "run", "python", "auto_batch_register_and_sync.py", "12", "--proxy", "--email-provider", "tempmail"])

print("\n" + "="*60)
print("🎉 HOÀN TẤT ĐĂNG KÝ TOÀN BỘ 25 TÀI KHOẢN!")
print("="*60)
