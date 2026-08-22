# 🚀 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG GROK2API SERVER

## 🌐 1. THÔNG TIN HỆ THỐNG VÀ DOMAIN CỐ ĐỊNH

* **Domain chính**: `https://api.grokapi.cyou`
* **Dashboard Quản Lý**: [https://api.grokapi.cyou/dashboard](https://api.grokapi.cyou/dashboard)
  - **Tài khoản & mật khẩu**: Xem trong file `.env` (biến `GROK2API_USER` / `GROK2API_PASS`)
* **API Key**: Tạo trên Dashboard → Settings → API Keys

---

## 🎨 2. CÁCH GỌI API TẠO ẢNH (POSTMAN / CODE)

* **Endpoint**: `POST https://api.grokapi.cyou/v1/images/generations`
* **Headers**:
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer <API_KEY_CỦA_BẠN>`
* **Body (JSON)**:
```json
{
  "model": "grok-imagine-image",
  "prompt": "a futuristic cyberpunk cat samurai in tokyo neon street, 8k digital art"
}
```

* **Kết quả trả về**:
```json
{
  "created": 1787218099,
  "data": [
    {
      "url": "https://api.grokapi.cyou/v1/media/images/img_xxx..."
    }
  ]
}
```
*(Ảnh đã được daemon tự động xóa sạch Watermark logo 🪐 Grok trước khi trả về!)*

---

## ⚡ 3. CÁCH TỰ ĐỘNG ĐĂNG KÝ THÊM TÀI KHOẢN GROK (TỰ TÍNH LUỒNG TỐI ƯU)

Hệ thống đã được tích hợp **AI Auto-Tuning**: Bạn **chỉ cần nhập số lượng tài khoản**, hệ thống sẽ tự tính toán số luồng song song phù hợp nhất để vừa chạy nhanh nhất vừa không làm nghẽn mạng hay tràn RAM:

```powershell
# 🚀 Đăng ký 10 tài khoản (Hệ thống tự chia 4 luồng song song, chỉ mất ~1.5 - 2 phút):
uv run python auto_batch_register_and_sync.py 10 --direct

# 🟣 Đăng ký 20 tài khoản qua xoay IP Proxy (Tự động chạy 5 luồng):
uv run python auto_batch_register_and_sync.py 20 --proxy

# (Tùy chọn) Nếu bạn muốn tự ép số luồng theo ý mình:
uv run python auto_batch_register_and_sync.py 10 --threads 5 --direct
```

---

## 🧹 4. KIỂM TRA & DỌN DẸP TÀI KHOẢN HẾT HẠN

```powershell
# Quét và tự động xóa tài khoản chết:
uv run python check_and_clean_accounts.py
```

> **Lưu ý**: Watermark Daemon đã tích hợp sẵn auto-cleanup mỗi 6 giờ. Bạn chỉ cần chạy lệnh trên khi muốn dọn dẹp ngay lập tức.

---

## 💎 5. CHUYỂN ĐỔI SANG GROK BUILD OAUTH (1-CLICK DUY NHẤT)

Nếu bạn muốn chuyển đổi dàn tài khoản SSO sang OAuth Build để tự động gia hạn token vĩnh viễn và mở khóa thêm **`grok-4.5`**, **`grok-4.6`**, **`grok-composer-2.5-fast`**:

```powershell
# Chạy chuyển đổi đa luồng song song (3 - 5 trình duyệt chạy đồng thời, tự động nạp Server):
uv run python sso_to_cpa.py --all --threads 3
```

---

## 🖥️ 6. KHỞI ĐỘNG HỆ THỐNG (MỖI KHI BẬT MÁY TÍNH)

Chỉ cần **click đúp vào file `START_GROK_SERVER.bat`** trong thư mục dự án:
1. Tự khởi động Watermark Daemon + Auto-Cleanup
2. Tự khởi động Backend Grok2API
3. Tự chờ backend sẵn sàng (health check)
4. Tự kết nối Cloudflare Tunnel vào domain `api.grokapi.cyou`
