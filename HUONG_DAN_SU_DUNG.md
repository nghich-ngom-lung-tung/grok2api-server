# 🚀 HƯỚNG DẪN SỬ DỤNG HỆ THỐNG GROK2API SERVER

## 🌐 1. THÔNG TIN HỆ THỐNG VÀ DOMAIN CỐ ĐỊNH

* **Domain chính**: `https://api.grokapi.cyou`
* **Dashboard Quản Lý**: [https://api.grokapi.cyou/dashboard](https://api.grokapi.cyou/dashboard)
  - **Tài khoản**: `admin`
  - **Mật khẩu**: `adminpassword123`
* **API Key hiện tại**: `g2a_23add0565c43_0huEvba19LTk2yQbvMQlSchQlVyVzYNr` *(Hoặc tạo thêm trên Dashboard)*

---

## 🎨 2. CÁCH GỌI API TẠO ẢNH (POSTMAN / CODE)

* **Endpoint**: `POST https://api.grokapi.cyou/v1/images/generations`
* **Headers**:
  - `Content-Type`: `application/json`
  - `Authorization`: `Bearer g2a_23add0565c43_0huEvba19LTk2yQbvMQlSchQlVyVzYNr`
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

## ⚡ 3. CÁCH TỰ ĐỘNG ĐĂNG KÝ THÊM TÀI KHOẢN GROK

Khi muốn đăng ký thêm tài khoản mới và nạp tự động vào hệ thống:

```powershell
# Đăng ký 10 tài khoản qua xoay IP Proxy (tự động test proxy sống trước khi đăng ký):
uv run python auto_batch_register_and_sync.py 10 --proxy

# Hoặc đăng ký qua mạng trực tiếp:
uv run python auto_batch_register_and_sync.py 5 --direct
```

---

## 🖥️ 4. KHỞI ĐỘNG HỆ THỐNG (MỖI KHI BẬT MÁY TÍNH)

Chỉ cần **click đúp vào file `START_GROK_SERVER.bat`** trong thư mục dự án:
1. Tự khởi động Watermark Daemon
2. Tự khởi động Backend Grok2API
3. Tự kết nối Cloudflare Tunnel vào domain `api.grokapi.cyou`
