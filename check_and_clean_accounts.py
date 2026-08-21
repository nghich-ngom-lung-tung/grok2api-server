"""
check_and_clean_accounts.py — Kiểm tra & tự động dọn dẹp tài khoản hết hạn / lỗi
──────────────────────────────────────────────────────────────────────────────────
Quét toàn bộ tài khoản trong Grok2API, phân loại Active vs Expired/Reauth,
và tự động xóa các tài khoản chết khỏi Database.

Cách dùng:
    uv run python check_and_clean_accounts.py
"""
import sys
import time
import requests
from common import get_base_url, get_admin_token

BASE_URL = get_base_url()

print("=" * 65)
print("🔍 BẮT ĐẦU KIỂM TRA & TỰ ĐỘNG DỌN DẸP TÀI KHOẢN HẾT HẠN / LỖI")
print("=" * 65)

token = get_admin_token()
if not token:
    print("[❌] Server Grok2API chưa được bật. Vui lòng chạy START_GROK_SERVER.bat trước!")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

# 1. Quét làm mới hạn ngạch & trạng thái toàn bộ tài khoản
print("\n[*] 1. Đang gửi lệnh quét & cập nhật trạng thái toàn bộ tài khoản...")
try:
    r_refresh = requests.post(
        f"{BASE_URL}/api/admin/v1/accounts/web/refresh-quotas",
        headers=headers,
        timeout=30,
    )
    print(f"    -> Đã cập nhật trạng thái kiểm tra (Status: {r_refresh.status_code})")
except Exception as e:
    print(f"    [!] Lỗi quét trạng thái: {e}")

time.sleep(2)

# 2. Lấy danh sách tài khoản
print("\n[*] 2. Đang phân tích danh sách tài khoản...")
r_list = requests.get(
    f"{BASE_URL}/api/admin/v1/accounts?pageSize=500",
    headers=headers,
    timeout=20,
)
if r_list.status_code != 200:
    print(f"[❌] Lấy danh sách tài khoản thất bại ({r_list.status_code})")
    sys.exit(1)

accounts = r_list.json().get("data", {}).get("items", [])
total = len(accounts)

active_list = []
expired_list = []

for acc in accounts:
    acc_id = acc.get("id")
    name = acc.get("name") or str(acc_id)
    auth_status = acc.get("authStatus", "active")

    if auth_status in ("reauthRequired", "disabled", "invalid"):
        expired_list.append((acc_id, name, auth_status))
    else:
        active_list.append((acc_id, name))

print(f"\n📊 KẾT QUẢ PHÂN TÍCH:")
print(f"  🟢 Tài khoản SỐNG KHỎE (Active): {len(active_list)} / {total}")
print(f"  🔴 Tài khoản HẾT HẠN / LỖI (Expired/Reauth): {len(expired_list)} / {total}")

if expired_list:
    print("\n🚨 DANH SÁCH TÀI KHOẢN HẾT HẠN CẦN XÓA:")
    for acc_id, name, st in expired_list:
        print(f"  - ID: {acc_id} | Name/Email: {name} | Trạng thái: {st}")

    print("\n[*] 3. Tiến hành tự động xóa các tài khoản chết khỏi Grok2API...")
    deleted_count = 0
    for acc_id, name, _ in expired_list:
        try:
            del_r = requests.delete(
                f"{BASE_URL}/api/admin/v1/accounts/{acc_id}",
                headers=headers,
                timeout=10,
            )
            if del_r.status_code in (200, 204):
                deleted_count += 1
                print(f"    [✓] Đã xóa: ID {acc_id} ({name})")
            else:
                print(f"    [!] Lỗi xóa ID {acc_id} (HTTP {del_r.status_code})")
        except Exception as e:
            print(f"    [!] Lỗi kết nối khi xóa ID {acc_id}: {e}")

    print(f"\n✨ Đã dọn dẹp thành công {deleted_count} tài khoản hết hạn khỏi Database!")
else:
    print(
        "\n🎉 Tuyệt vời! Toàn bộ tài khoản hiện tại đều đang sống khỏe 100%, "
        "không có tài khoản nào bị chết!"
    )

print("\n" + "=" * 65)
print("🏁 HOÀN TẤT KIỂM TRA & DỌN DẸP!")
print("=" * 65)
