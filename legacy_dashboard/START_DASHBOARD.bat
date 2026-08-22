@echo off
chcp 65001 > nul
title Grok Imagine Dashboard & API Gateway
cd /d "%~dp0"

echo ========================================================
echo   🚀 ĐANG KHỞI ĐỘNG GROK IMAGINE DASHBOARD & API SERVER
echo ========================================================
echo.
echo   🌐 Web Dashboard: http://127.0.0.1:8000
echo   🔌 OpenAI Image API: http://127.0.0.1:8000/v1/images/generations
echo   🛡️ Quản Lý API Key & Bảo Mật: Tab trên Dashboard
echo.
echo ========================================================
echo.

:: Tự động mở trình duyệt sau 2 giây
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"

:: Chạy server FastAPI
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe server.py
) else (
    uv run python server.py
)

pause
