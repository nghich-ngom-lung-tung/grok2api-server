@echo off
chcp 65001 > nul
title Grok2API Server - api.grokapi.cyou
cd /d "%~dp0"

echo ========================================================
echo   🚀 KHỞI ĐỘNG HỆ THỐNG GROK2API (https://api.grokapi.cyou)
echo ========================================================
echo.

:: 1. Khởi động watermark daemon (kèm auto-cleanup mỗi 6h)
echo [1/3] Đang khởi động Watermark Daemon + Auto-Cleanup...
start /b uv run python watermark_daemon.py

:: 2. Khởi động grok2api backend
echo [2/3] Đang khởi động Grok2API Backend (Port 8080)...
start /b cmd /c "cd /d grok2api_repo\backend && grok2api.exe --config ../config.yaml"

:: 3. Chờ backend thực sự sẵn sàng trước khi bật tunnel
echo [..] Đang chờ Backend khởi động hoàn tất...
set /a WAIT_COUNT=0
:wait_ready
curl -s http://127.0.0.1:8080/healthz >nul 2>&1
if errorlevel 1 (
    set /a WAIT_COUNT+=1
    if %WAIT_COUNT% GEQ 30 (
        echo [!] Backend không phản hồi sau 60 giây. Vui lòng kiểm tra lỗi.
        pause
        exit /b 1
    )
    timeout /t 2 >nul
    goto wait_ready
)
echo [OK] Backend đã sẵn sàng trên port 8080!

:: 4. Khởi động Cloudflare Named Tunnel
echo [3/3] Đang kết nối Cloudflare Tunnel (api.grokapi.cyou)...
start /b cmd /c "cloudflared tunnel run grokapi"

echo.
echo ========================================================
echo   ✅ HỆ THỐNG ĐÃ HOẠT ĐỘNG HOÀN HẢO!
echo.
echo   🌐 Dashboard: https://api.grokapi.cyou/dashboard
echo   🔑 API URL:   https://api.grokapi.cyou/v1/images/generations
echo   🧹 Auto-Cleanup: Mỗi 6 giờ tự dọn tài khoản hết hạn
echo ========================================================
echo.
echo (Đừng tắt cửa sổ này để server tiếp tục chạy nhé)
pause
