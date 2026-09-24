@echo off
chcp 65001 >nul
setlocal EnableExtensions

if /I not "%~1"=="UNINSTALL" (
  echo 用法: scripts\uninstall_ngrok_service.bat UNINSTALL
  echo 會停止並移除 ngrok 官方 service（若存在），以及工作排程：
  echo   AttendanceFastAPI
  echo   AttendanceNgrok
  exit /b 1
)

where ngrok >nul 2>&1
if not errorlevel 1 (
  ngrok service stop
  ngrok service uninstall
)

schtasks /Delete /TN "AttendanceFastAPI" /F
schtasks /Delete /TN "AttendanceNgrok" /F

echo 已嘗試移除開機啟動項目。FastAPI 若仍在執行，請用 scripts\stop_production.bat。
exit /b 0
