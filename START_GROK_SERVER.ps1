# PowerShell Launcher for Grok2API Server
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "Grok2API Master Server - api.grokapi.cyou"
Set-Location -Path $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  🚀 KHỞI ĐỘNG TOÀN BỘ HỆ THỐNG GROK2API" -ForegroundColor Green
Write-Host "     Domain chính: https://api.grokapi.cyou" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Watermark Daemon
Write-Host "[1/4] Đang bật Watermark Daemon (Khử logo + 4K Upscaler)..." -ForegroundColor Magenta
Start-Process -WindowStyle Minimized -FilePath "cmd.exe" -ArgumentList "/c cd /d `"$PSScriptRoot`" && uv run python watermark_daemon.py"

# 2. Browser Gateway
Write-Host "[2/4] Đang bật Browser Gateway (Port 8085 - Sửa ảnh & Video)..." -ForegroundColor Magenta
Start-Process -WindowStyle Minimized -FilePath "cmd.exe" -ArgumentList "/c cd /d `"$PSScriptRoot`" && uv run python browser_gateway.py"

# 3. Backend Grok2API
Write-Host "[3/4] Đang bật Backend Grok2API (Port 8080 - Chat & Vẽ ảnh)..." -ForegroundColor Magenta
Start-Process -WindowStyle Minimized -FilePath "cmd.exe" -ArgumentList "/c cd /d `"$PSScriptRoot\grok2api_repo\backend`" && grok2api.exe --config ../config.yaml"

# Wait for backend
Write-Host "[..] Đang kiểm tra kết nối Backend 8080..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $res = Invoke-RestMethod -Uri "http://127.0.0.1:8080/healthz" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res) { $ready = $true; break }
    } catch {}
}

if ($ready) {
    Write-Host "[OK] Backend Grok2API đã sẵn sàng!" -ForegroundColor Green
} else {
    Write-Host "[!] Backend đang khởi động ngầm, tiếp tục kết nối Tunnel..." -ForegroundColor Yellow
}

# 4. Cloudflared Tunnel
Write-Host "[4/4] Đang kết nối Cloudflare Tunnel (api.grokapi.cyou)..." -ForegroundColor Magenta
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
Start-Process -WindowStyle Minimized -FilePath "cmd.exe" -ArgumentList "/c cloudflared tunnel run grokapi"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ✅ HỆ THỐNG ĐÃ HOẠT ĐỘNG HOÀN HẢO TRÊN CLOUD!" -ForegroundColor Green
Write-Host ""
Write-Host "  🌐 Dashboard quản lý:  https://api.grokapi.cyou/dashboard" -ForegroundColor White
Write-Host "  🔑 API Vẽ ảnh (Text):  https://api.grokapi.cyou/v1/images/generations" -ForegroundColor White
Write-Host "  🎨 API Sửa ảnh (Edit):  https://api.grokapi.cyou/v1/images/edits" -ForegroundColor White
Write-Host "  🎬 API Tạo Video:      https://api.grokapi.cyou/v1/videos/generations" -ForegroundColor White
Write-Host "  🧹 Auto-Cleanup:       Mỗi 6 giờ tự động dọn dẹp tài khoản" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "(Lưu ý: Giữ cửa sổ này để hệ thống tiếp tục hoạt động)" -ForegroundColor Yellow
Read-Host "Nhấn Enter để dừng và thoát..."
