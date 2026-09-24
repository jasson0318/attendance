@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 出勤打卡系統 - 停止監聽 :8800 的 FastAPI / uvicorn

echo ========================================
echo   出勤打卡系統 - 停止服務
echo ========================================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$conns = @(Get-NetTCPConnection -LocalPort 8800 -State Listen);" ^
  "if ($conns.Count -eq 0) { Write-Host '[訊息] 目前沒有行程在監聽 :8800。'; exit 0 };" ^
  "$ids = $conns | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "foreach ($procId in $ids) {" ^
  "  $p = Get-Process -Id $procId -ErrorAction SilentlyContinue;" ^
  "  if ($p) { Write-Host ('[停止] PID=' + $procId + ' Name=' + $p.ProcessName); Stop-Process -Id $procId -Force }" ^
  "  else { Write-Host ('[停止] PID=' + $procId) }" ^
  "};" ^
  "Start-Sleep -Seconds 1;" ^
  "$left = @(Get-NetTCPConnection -LocalPort 8800 -State Listen);" ^
  "if ($left.Count -gt 0) { Write-Host '[警告] :8800 仍有監聽行程，請以系統管理員權限再試。'; exit 1 }" ^
  "else { Write-Host '[完成] :8800 已釋放。'; exit 0 }"

exit /b %ERRORLEVEL%
