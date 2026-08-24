# 🚀 HƯỚNG DẪN SỬ DỤNG TOÀN DIỆN HỆ THỐNG GROK API & AGENT

> **Hệ sinh thái Grok Reverse-Engineered hoàn chỉnh**: Hỗ trợ OpenAI API (Chat/Code/Image/Video), Native ACP Agent cho Grok Build IDE, Dòng lệnh Grok CLI và Bộ tự động nuôi tài khoản.

---

## 🌐 1. THÔNG TIN KẾT NỐI VÀ XÁC THỰC

* **Domain chính thức (HTTPS)**: `https://api.grokapi.cyou/v1`
* **Localhost (Nội bộ)**: `http://127.0.0.1:8085/v1`
* **API Key mặc định**: `g2a_03d12f690dbf_FMCDddgQLRf-3Y1TnmmBM9anlwoWBHqf`
* **Header bắt buộc khi gọi API**:
  ```http
  Authorization: Bearer g2a_03d12f690dbf_FMCDddgQLRf-3Y1TnmmBM9anlwoWBHqf
  Content-Type: application/json
  ```

---

## 🖥️ 2. KHỞI ĐỘNG HỆ THỐNG (MỖI KHI BẬT MÁY)

### 🔹 Cách 1: Chạy 1-Click (Khuyên dùng)
Click đúp vào file:
```
START_GROK_SERVER.bat
```
*(Hoặc click chuột phải vào `START_GROK_SERVER.ps1` chọn **Run with PowerShell**)*.

### 🔹 Cách 2: Khởi động từng service bằng dòng lệnh:
```powershell
# 1. Bật Smart Gateway (Port 8085):
uv run python browser_gateway.py

# 2. Bật Watermark Cleaner Daemon (Xóa logo tự động):
uv run python watermark_daemon.py

# 3. Kết nối Cloudflare Tunnel ra internet:
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run grokapi
```

---

## ⚡ 3. QUÉT & LỌC PROXY SIÊU TỐC (FAST SCAN PROXY)

Dùng để quét và lọc danh sách proxy sống từ `proxies.txt` với tốc độ cao (50-100 luồng song song), tự động lưu proxy tốt nhất vào `good_proxies.txt`:

```powershell
# 🚀 Quét proxy mặc định (50 luồng):
uv run python fast_scan.py

# ⚡ Quét siêu tốc với 100 luồng:
uv run python fast_scan.py 100
```
> **Định dạng trong `proxies.txt`**: Mỗi dòng một proxy dạng `ip:port` hoặc `ip:port:user:password`.

---

## 👥 4. TỰ ĐỘNG ĐĂNG KÝ THÊM TÀI KHOẢN (AUTO-REPLENISH)

Hệ thống tích hợp **AI Auto-Tuning**: Bạn chỉ cần nhập số lượng tài khoản, hệ thống sẽ tự động chia luồng tối ưu:

```powershell
# 🚀 Đăng ký 10 tài khoản Direct (Tự chia 4 luồng song song, mất ~1.5 phút):
uv run python auto_batch_register_and_sync.py 10 --direct

# 🟣 Đăng ký 20 tài khoản qua xoay IP Proxy:
uv run python auto_batch_register_and_sync.py 20 --proxy

# ⚙️ Tự ép số luồng theo ý bạn:
uv run python auto_batch_register_and_sync.py 10 --threads 5 --direct
```

---

## 💻 5. CÔNG CỤ DÒNG LỆNH GROK CLI (COMMAND LINE)

Bạn có thể mở PowerShell / Command Prompt ở bất kỳ đâu và gõ:

```powershell
# 1. Trò chuyện nhanh:
grok "Giải thích nguyên lý hoạt động của Docker trong 3 gạch đầu dòng"

# 2. Tạo ảnh 4K nghệ thuật (Tự động mở ảnh sau khi tạo):
grok --img "Cyberpunk neon samurai riding futuristic motorcycle in rain, 8k"

# 3. Phân tích hình ảnh (Vision AI):
grok --vision photo.png "Ảnh này chụp gì và có lỗi gì không?"

# 4. Mở phiên Chat tương tác liên tục:
grok -i
```

---

## 🛠️ 6. SỬ DỤNG TRONG GROK BUILD IDE (WORKBENCH ACP)

1. Mở **Grok Build IDE** (`D:\Grok-Build-IDE\Grok Build IDE.exe`).
2. Mở thanh chat **Grok Build Workbench** bên trái (hoặc bấm `Ctrl+Shift+P` → chọn `Grok Build: Focus on Chat View`).
3. **Chọn Model**: Dưới ô nhập chat có menu chọn model:
   * `grok-4.5` (Toàn diện, thông minh nhất)
   * `grok-4.6` (Bản tối ưu logic & code mới)
   * `grok-2.5-fast` (Phản hồi siêu tốc)
   * `grok-code` (Chuyên gia viết & sửa code)
4. **Hỗ trợ Đọc & Code Repo**: Bạn có thể hỏi:
   * *"Đọc và tóm tắt repo này"*
   * *"Giải thích hàm X trong file Y"*
   * *"Viết cho tôi tính năng Z..."*

---

## 📡 7. TOÀN BỘ DANH SÁCH REST API (CALL QUA POSTMAN / CODE)

### A. Chat & Code Completions
* **Endpoint**: `POST https://api.grokapi.cyou/v1/chat/completions`
* **Body (Stream hoặc Non-stream)**:
```json
{
  "model": "grok-4.6",
  "messages": [
    {"role": "user", "content": "Xin chào Grok! Hãy viết 1 bài thơ ngắn."}
  ],
  "stream": false
}
```

### B. Tạo ảnh mới (Text-to-Image)
* **Endpoint**: `POST https://api.grokapi.cyou/v1/images/generations`
```json
{
  "prompt": "A majestic dragon flying over snowy mountain peak, 8k digital art"
}
```

### C. Redesign & Sửa ảnh (Image-to-Image / Edit)
* **Endpoint**: `POST https://api.grokapi.cyou/v1/images/edits`
```json
{
  "image": "https://example.com/original_image.jpg",
  "prompt": "Redesign this character into a golden cyberpunk robotic knight, 8k"
}
```

### D. Tạo Video Chuyển động (Video Generation)
* **Endpoint**: `POST https://api.grokapi.cyou/v1/videos/generations`
```json
{
  "prompt": "Cinematic slow motion of a neon tiger walking through futuristic forest",
  "duration": 5,
  "aspect_ratio": "16:9"
}
```
* **Polling trạng thái Video**: `GET https://api.grokapi.cyou/v1/videos/{request_id}`

### E. Xem File Ảnh & Video Trực Tiếp
* **Xem ảnh**: `GET https://api.grokapi.cyou/v1/media/images/{asset_id}`
* **Xem video**: `GET https://api.grokapi.cyou/v1/media/videos/{filename}`
