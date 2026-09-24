@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 正式部署前檢查（只回報，不改系統設定）

cd /d "%~dp0.."
if errorlevel 1 (
  echo [錯誤] 無法切換到專案目錄。
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo [FAIL] python — 找不到 python。請先安裝 Python 3.12+ 並加入 PATH。
  echo 本腳本不會自動安裝 Python。
  exit /b 1
)

python scripts\preflight_check.py
exit /b %ERRORLEVEL%
