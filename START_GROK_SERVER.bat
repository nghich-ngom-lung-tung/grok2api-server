@echo off
title Grok2API Master Server - api.grokapi.cyou
cd /d "%~dp0"

echo ========================================================
echo   [GROK2API SERVER] - https://api.grokapi.cyou
echo ========================================================
echo.

:: 1. Watermark Daemon + 4K Super-Resolution
echo [1/4] Starting Watermark Daemon (4K Upscaler)...
start "Grok2API - Watermark Daemon" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "cd '%~dp0'; uv run python watermark_daemon.py"

:: 2. Browser Gateway (Port 8085)
echo [2/4] Starting Browser Gateway (Port 8085 - Image Edit ^& Video)...
start "Grok2API - Browser Gateway" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "cd '%~dp0'; uv run python browser_gateway.py"

:: 3. Grok2API Backend (Port 8080)
echo [3/4] Starting Grok2API Backend (Port 8080 - Chat ^& Text-to-Image)...
start "Grok2API - Backend 8080" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "cd '%~dp0grok2api_repo\backend'; .\grok2api.exe --config ../config.yaml"

:: 4. Cloudflare Named Tunnel
echo [4/4] Connecting Cloudflare Tunnel (api.grokapi.cyou)...
start "Grok2API - Cloudflare Tunnel" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User'); cloudflared tunnel run grokapi"

echo.
echo ========================================================
echo   [OK] HE THONG DANG CHAY HOAN HAO TREN CLOUD!
echo.
echo   * Dashboard:        https://api.grokapi.cyou/dashboard
echo   * API Ve anh:       https://api.grokapi.cyou/v1/images/generations
echo   * API Sua anh:      https://api.grokapi.cyou/v1/images/edits
echo   * API Tao Video:    https://api.grokapi.cyou/v1/videos/generations
echo   * Auto-Cleanup:     Tu dong don tai khoan moi 6 gio
echo ========================================================
echo.
echo [Luu y] Khong tat cua so nay de server tiep tuc hoat dong.
echo.
pause
