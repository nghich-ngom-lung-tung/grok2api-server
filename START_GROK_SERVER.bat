@echo off
chcp 65001 > nul
title Grok2API Server - api.grokapi.cyou
cd /d "%~dp0"

echo ========================================================
echo   🚀 KHỞI ĐỘNG HỆ THỐNG GROK2API (https://api.grokapi.cyou)
echo ========================================================
echo.

:: 1. Khởi động watermark daemon
echo [1/3] Đang khởi động Watermark Daemon...
start /b uv run python watermark_daemon.py

:: 2. Khởi động grok2api backend
echo [2/3] Đang khởi động Grok2API Backend (Port 8080)...
start /b cmd /c "cd /d grok2api_repo\backend && grok2api.exe --config ../config.yaml"

:: 3. Khởi động Cloudflare Named Tunnel
echo [3/3] Đang kết nối Cloudflare Tunnel (api.grokapi.cyou)...
start /b cmd /c "cloudflared tunnel run grokapi"

echo.
echo ========================================================
echo   ✅ HỆ THỐNG ĐÃ HOẠT ĐỘNG HOÀN HẢO!
echo.
echo   🌐 Dashboard: https://api.grokapi.cyou/dashboard
echo   🔑 API URL:   https://api.grokapi.cyou/v1/images/generations
echo ========================================================
echo.
echo (Đừng tắt cửa sổ này để server tiếp tục chạy nhé)
pause
