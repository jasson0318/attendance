@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 在正式電腦首次部署時安裝 Python 套件

cd /d "%~dp0.."
if errorlevel 1 (
  echo [錯誤] 無法切換到專案目錄。
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 python。請先安裝 Python 3.12+ 並勾選 Add to PATH。
  exit /b 1
)

echo 正在安裝 requirements.txt ...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [錯誤] 套件安裝失敗。
  exit /b 1
)

if exist "scripts\generate_icons.py" (
  echo 產生 PWA 圖示...
  python scripts\generate_icons.py
)

echo.
echo [完成] 套件已安裝。接著可執行 scripts\start_production.bat
exit /b 0
