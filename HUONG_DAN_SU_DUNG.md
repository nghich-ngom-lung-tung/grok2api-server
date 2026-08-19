# 🚀 HƯỚNG DẪN SỬ DỤNG TOOL REG NICK GROK (xAI) CHI TIẾT TỪ A-Z

Tài liệu hướng dẫn toàn bộ quy trình: từ quét lọc Proxy tốc độ cao, cấu hình email, cho đến tạo tài khoản xAI (Grok) tự động 100% miễn phí.

---

## 📑 MỤC LỤC
1. [Cơ chế hoạt động](#1-cơ-chế-hoạt-động)
2. [Cài đặt môi trường](#2-cài-đặt-môi-trường)
3. [Bước 1: Quét & Lọc Proxy sống siêu tốc (100 Threads)](#3-bước-1-quét--lọc-proxy-sống-siêu-tốc)
4. [Bước 2: Hướng dẫn tạo tài khoản (Reg Nick)](#4-bước-2-hướng-dẫn-tạo-tài-khoản-reg-nick)
   - [Cách A: Dùng Mail tạm Mail.tm (@emalupe.com) - KHUYÊN DÙNG](#cách-a-dùng-mailtm-emalupecom---khuyên-dùng)
   - [Cách B: Dùng Gmail chính chủ (+alias)](#cách-b-dùng-gmail-chính-chủ-alias)
   - [Cách C: Dùng Proxy xoay tua từ danh sách vừa quét](#cách-c-dùng-proxy-xoay-tua-từ-danh-sách-đã-quét)
5. [Bước 3: Lấy tài khoản & SSO Token sau khi reg](#5-bước-3-lấy-tài-khoản--sso-token-sau-khi-reg)
6. [Bước 4: Mở Web Dashboard & Cổng API Tạo Ảnh Local](#6-bước-4-mở-web-dashboard--cổng-api-tạo-ảnh-local)
7. [Bước 5: Chuyển đổi SSO sang OAuth Token (Tùy chọn)](#7-bước-5-chuyển-đổi-sso-sang-oauth-token-nếu-dùng-api)
8. [Bảng tra cứu lỗi thường gặp & Cách xử lý](#8-bảng-tra-cứu-lỗi-thường-gặp--cách-xử-lý)

---

## 1. Cơ chế hoạt động
- **Giải Captcha Turnstile:** Sử dụng trình duyệt Chrome điều khiển qua `DrissionPage` để giải Cloudflare Turnstile **100% MIỄN PHÍ** (không tốn tiền mua key YesCaptcha).
- **Gửi & Nhận OTP:** Giao tiếp trực tiếp bằng giao thức **gRPC-web** với xAI giúp gửi và xác thực mã OTP cực nhanh.
- **Tự động đọc mã OTP:** Tự động kết nối IMAP (với Gmail) hoặc API (với Mail.tm) để đọc mã OTP gửi về và điền vào form mà bạn không cần thao tác tay.
- **Bóc tách Token:** Tự động bắt SSO Token và lưu vào thư mục `keys/`.

---

## 2. Cài đặt môi trường

Dự án sử dụng công cụ quản lý package siêu tốc **`uv`**.

### Lệnh chạy với `uv`:
Mỗi khi chạy bất kỳ file script nào, luôn thêm tiền tố `uv run`:
```powershell
uv run python <tên_file.py>
```

*(Nếu chưa cài thư viện, `uv` sẽ tự động tải và đồng bộ đúng môi trường ảo `.venv`)*.

---

## 3. Bước 1: Quét & Lọc Proxy sống siêu tốc

Nếu bạn có danh sách hàng nghìn Proxy công cộng (HTTP / SOCKS5 / SOCKS4) và muốn lọc ra những con còn sống để dùng:

1. Mở file **`proxies.txt`** và dán toàn bộ danh sách proxy vào (mỗi dòng một IP:Port, ví dụ: `103.188.169.93:8080` hoặc `socks5://191.223.220.23:1080`).
2. Mở terminal và chạy lệnh:
   ```powershell
   uv run fast_scan.py
   ```
3. **Kết quả:**
   - Script sẽ quét song song **100 luồng siêu tốc**, tự động test khả năng kết nối tới `accounts.x.ai`.
   - Các proxy sống sẽ được tự động lưu vào **`good_proxies.txt`** (kèm đúng định dạng `http://...` hoặc `socks5://...`).
   - File `proxies.txt` sẽ tự động dọn sạch để sẵn sàng cho đợt dán IP tiếp theo.

---

## 4. Bước 2: Hướng dẫn tạo tài khoản (Reg Nick)

Tool hỗ trợ script chính là **`grok_free.py`**.

### Cách A: Dùng Mail.tm (`@emalupe.com`) - KHUYÊN DÙNG ⭐
> **Ưu điểm:** Hoàn toàn miễn phí, mỗi tài khoản là 1 email độc lập, **không bao giờ bị xAI rate-limit** do gửi quá nhiều mã vào 1 email.

Chạy lệnh:
```powershell
uv run python grok_free.py --count 5 --email-provider mailtm --direct
```
*(Thay số `5` bằng số lượng tài khoản bạn muốn tạo)*.

---

### Cách B: Dùng Gmail chính chủ (+alias)
> **Ưu điểm:** Độ tin cậy tài khoản cao nhất (thuộc sở hữu chính chủ của bạn).
> **Lưu ý:** Nếu tạo liên tục 3-4 nick thì xAI có thể tạm khóa gửi OTP trong 2-5 phút để chống spam.

1. Đảm bảo file `.env` đã có cấu hình Gmail của bạn:
   ```env
   EMAIL_PROVIDER="gmail"
   GMAIL_BASE_EMAIL="email_cua_ban@gmail.com"
   GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"  # Mật khẩu ứng dụng 16 chữ cái tạo từ Google Account
   ```
2. Chạy lệnh:
   ```powershell
   uv run python grok_free.py --count 1 --email-provider gmail --direct
   ```

---

### Cách C: Dùng Proxy xoay tua từ danh sách đã quét
Nếu bạn muốn đổi IP liên tục qua danh sách proxy đã lưu trong `good_proxies.txt`:

```powershell
uv run python grok_free.py --count 5 --email-provider mailtm
```
*(Bỏ cờ `--direct` đi thì tool sẽ tự động bốc ngẫu nhiên Proxy HTTP/SOCKS5 sống trong `good_proxies.txt` để đổi IP)*.

---

### ⚙️ Bảng tổng hợp các tham số dòng lệnh hữu ích:

| Tham số | Ý nghĩa | Ví dụ |
|---|---|---|
| `--count N` | Số lượng tài khoản muốn đăng ký (mặc định: 3) | `--count 10` |
| `--email-provider` | Chọn loại email: `mailtm`, `gmail`, `luckmail`, `outlook` | `--email-provider mailtm` |
| `--direct` hoặc `--no-proxy` | Dùng mạng trực tiếp (Direct) không qua proxy | `--direct` |
| `--headless` | Chạy ẩn trình duyệt Chrome dưới nền | `--headless` |
| `--min-delay N` | Thời gian nghỉ tối thiểu giữa 2 lần reg (giây) | `--min-delay 10` |
| `--max-delay N` | Thời gian nghỉ tối đa giữa 2 lần reg (giây) | `--max-delay 20` |

---

## 5. Bước 3: Lấy tài khoản & SSO Token sau khi reg

Mỗi khi tạo thành công 1 tài khoản, dữ liệu sẽ tự động được ghi nối tiếp vào thư mục **`keys/`**:

- **`keys\accounts.txt`**: Danh sách tài khoản dạng:
  ```text
  email:password:sso_token
  ```
  *(Ví dụ: `groklyyzmzivfh@emalupe.com:5onhbx1spgw7xwAa1!:eyJ0eXAiOi...`)*

- **`keys\grok.txt`**: Danh sách riêng các chuỗi **SSO Token** (tiện lợi để copy nạp vào API Gateway hoặc grok2api).

---

## 6. Bước 4: Mở Web Dashboard & Cổng API Tạo Ảnh Local

Tool đã tích hợp sẵn **Web Dashboard & API Gateway** chuẩn OpenAI:

### 1. Lệnh khởi chạy:
```powershell
uv run python server.py
```

### 2. Mở giao diện trên trình duyệt:
👉 Truy cập: **`http://localhost:8000`** hoặc **`http://127.0.0.1:8000`**

### 3. Tính năng có trong Dashboard:
- 📊 **Thống kê thời gian thực:** Xem tổng số nick trong kho, số token SSO đang sẵn sàng, tỷ lệ thành công và tốc độ tạo ảnh trung bình.
- 🎨 **Imagine Studio:** Trực tiếp gõ prompt và tạo ảnh ngay trên giao diện Web mà không cần gõ lệnh.
- 🖼️ **Lịch sử & Bộ sưu tập:** Xem lại toàn bộ ảnh đã tạo, prompt tương ứng, tải ảnh HD hoặc copy link.
- 🔑 **Quản lý tài khoản:** Xem danh sách toàn bộ email & pass, nút bấm 1-click **"Auto Reg 3 Nick"** để tự động tạo thêm nick trong nền.
- 🔌 **Cổng API chuẩn OpenAI:**
  - `POST http://127.0.0.1:8000/v1/images/generations` (DALL-E standard)
  - `POST http://127.0.0.1:8000/v1/chat/completions` (OpenAI Chat standard)

---

## 7. Bước 5: Chuyển đổi SSO sang OAuth Token (Nếu dùng API)

Nếu bạn cần dùng tài khoản cho các cổng API như [grok2api](https://github.com/chenyme/grok2api) hoặc kết nối qua OAuth Device Flow để gọi các model cao cấp (`grok-4.5`, `grok-4.6`):

Chạy lệnh:
```powershell
uv run python sso_to_cpa.py --all
```
Script sẽ đọc toàn bộ SSO Token trong `keys/grok.txt` và mint thành access token OAuth tương ứng.

---

## 7. Bảng tra cứu lỗi thường gặp & Cách xử lý

| Hiện tượng / Lỗi | Nguyên nhân | Cách khắc phục |
|---|---|---|
| `ModuleNotFoundError: No module named 'curl_cffi'` | Đang chạy bằng Python ngoài chưa kích hoạt môi trường ảo `.venv` | Luôn thêm `uv run` ở đầu lệnh, ví dụ: `uv run python grok_free.py` |
| `curl: (28) Failed to connect to ... port ... after 21000 ms` | Proxy miễn phí trong danh sách bị rớt mạng hoặc timeout | Thêm cờ `--direct` để chạy thẳng bằng mạng cá nhân, hoặc quét lại proxy mới bằng `uv run fast_scan.py` |
| `Too many validation codes sent to email [WKE=email:send-validation-code-rate-limited]` | Gửi quá nhiều mã OTP vào 1 địa chỉ Gmail trong thời gian ngắn | Chờ 3-5 phút để xAI reset giới hạn, hoặc chuyển sang dùng `--email-provider mailtm` |
| `This email domain has been rejected [WKE=account:email-domain-rejected]` | Đuôi domain của mail tạm bị xAI đưa vào danh sách chặn | Sử dụng đuôi `@emalupe.com` (mặc định đã được cấu hình trong `mailtm`) hoặc Gmail chính chủ |
| `Server action not found (404)` | Action ID bị cache cũ | Tool đã tích hợp sẵn cơ chế tự động quét Action ID mới nhất trực tiếp từ mã nguồn xAI |

---

*Chúc bạn tạo tài khoản Grok thành công và mượt mà!*
