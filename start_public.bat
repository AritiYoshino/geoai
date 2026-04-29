@echo off
chcp 65001 >nul
title GeoAI WebGIS - 公网访问启动器

echo ============================================
echo   GeoAI WebGIS 公网访问启动器
echo ============================================
echo.
echo [1/2] 启动 Web 服务器...
cd /d "%~dp0"
start "GeoAI Server" cmd /c "python main.py"
timeout /t 3 /nobreak >nul

echo.
echo [2/2] 启动 ngrok 公网隧道...
start "ngrok Tunnel" cmd /c "C:\Users\CLIENTS\ngrok\ngrok.exe http 8000"
timeout /t 2 /nobreak >nul

echo.
echo ✅ 服务已启动！
echo.
echo   本地访问: http://127.0.0.1:8000
echo   公网地址: 请查看 ngrok 窗口中的 Forwarding 行
echo.
echo   ⚠️ 关闭这两个窗口即停止服务
echo.
pause
