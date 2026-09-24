@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 只轉送本機 FastAPI :8800。不寫入 authtoken（請先用 ngrok config add-authtoken）。
REM 不暴露 SQLite、檔案分享、RDP 或其他 Windows 服務。

where ngrok >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 ngrok。請先依照 docs\NgrokSetup.md 安裝。
  exit /b 1
)

echo ========================================
echo   ngrok  -^>  http://127.0.0.1:8800
echo ========================================
echo 請先在另一個視窗啟動 FastAPI（scripts\start_production.bat）。
echo 畫面上的 Forwarding https://.... 就是公開 API 根網址。
echo 不要把該網址寫進原始碼；更新 GitHub Secret ATTENDANCE_API_BASE 後重新部署 Pages。
echo.

ngrok http 127.0.0.1:8800
exit /b %ERRORLEVEL%
