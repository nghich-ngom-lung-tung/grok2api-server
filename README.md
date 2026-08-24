# 🪐 Grok API & Autonomous Agent Suite

> **Hệ sinh thái API & AI Agent toàn diện cho Grok (xAI)**: Hỗ trợ OpenAI API (Chat/Code/Image/Video), Native ACP Agent cho Grok Build IDE, Dòng lệnh Grok CLI và Bộ tự động quản lý kho tài khoản.

---

## 🌟 Tính Năng Nổi Bật

- 🚀 **OpenAI Compatible REST API**: Thay thế hoàn hảo cho OpenAI (`/v1/chat/completions`, `/v1/images/generations`, `/v1/images/edits`, `/v1/videos/generations`).
- 🤖 **Native Grok Build IDE Integration**: Tích hợp giao thức **ACP (Agent Client Protocol)** trực tiếp vào IDE, tự động đọc và hiểu cấu trúc toàn bộ Repository.
- 🎨 **Tạo ảnh 4K & Redesign Ảnh**: Khử Watermark tự động, biến đổi ảnh nghệ thuật từ ảnh có sẵn.
- 🎬 **Tạo Video Chuyển Động**: Sinh video từ văn bản prompt và hình ảnh.
- ⚡ **Fast Proxy Scanner**: Quét và lọc danh sách proxy sống siêu tốc 50 - 100 luồng đồng thời.
- 👥 **Auto-Replenish Account Pool**: Tự động đăng ký và xoay vòng kho 84+ tài khoản Grok, không lo giới hạn lượt gọi.

---

## 🚀 Hướng Dẫn Bắt Đầu Nhanh

### 1. Khởi động 1-Click
Click đúp vào file `START_GROK_SERVER.bat` để bật toàn bộ hệ thống (Smart Gateway, Watermark Daemon và Cloudflare Tunnel).

### 2. Quét Proxy Nhanh
```bash
uv run python fast_scan.py 50
```

### 3. Đăng ký tài khoản tự động
```bash
uv run python auto_batch_register_and_sync.py 10 --direct
```

### 4. Sử dụng Grok CLI
```bash
grok "Xin chào!"
grok --img "A cyberpunk warrior, 8k"
grok -i
```

---

## 📖 Tài Liệu Chi Tiết
Xem toàn bộ hướng dẫn sử dụng và danh sách đầy đủ các API tại: [HUONG_DAN_SU_DUNG.md](file:///d:/nghich%20ng%E1%BB%A3m%20lung%20tung/GROK/HUONG_DAN_SU_DUNG.md).
