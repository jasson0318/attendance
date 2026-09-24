@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 出勤打卡系統 - 正式啟動（綁定 0.0.0.0:8800）
REM 請在「24 小時正式電腦」執行；本腳本亦可於開發電腦驗證。

cd /d "%~dp0.."
if errorlevel 1 (
  echo [錯誤] 無法切換到專案目錄。
  exit /b 1
)

set "ROOT=%CD%"
echo ========================================
echo   出勤打卡系統 - 正式啟動
echo ========================================
echo 專案目錄: %ROOT%
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 python。請先安裝 Python 3.12+ 並加入 PATH。
  exit /b 1
)

if not exist "%ROOT%\requirements.txt" (
  echo [錯誤] 找不到 requirements.txt
  exit /b 1
)

if not exist "%ROOT%\data" mkdir "%ROOT%\data"

REM 預先載入設定：必要時建立 data\.secret_key（已存在則不會重新產生）
python -c "from backend.app.config import HOST, PORT, SECRET_KEY, DATA_DIR; from pathlib import Path; sf=DATA_DIR/'.secret_key'; print('監聽位址:', HOST); print('連接埠  :', PORT); print('SECRET  :', '環境變數 ATTENDANCE_SECRET_KEY' if __import__('os').environ.get('ATTENDANCE_SECRET_KEY') else ('既有檔案 '+str(sf) if sf.exists() else '已建立 '+str(sf))); print('資料庫  :', DATA_DIR/'attendance.sqlite3')"
if errorlevel 1 (
  echo [錯誤] 無法載入 backend.app.config。請確認已安裝套件：
  echo   python -m pip install -r requirements.txt
  exit /b 1
)

echo.
echo 本機測試網址（正式電腦本機）:
echo   http://127.0.0.1:8800
echo   http://localhost:8800
echo.
echo 管理後台:
echo   http://127.0.0.1:8800/admin
echo.
echo 【正式】手機用 GitHub Pages；API 經 ngrok HTTPS 回到本機 :8800。見 docs\NgrokProduction.md
echo 【注意】區網 IP（例如 192.168.x.x:8800）僅供同網段測試，
echo         不是 4 間門市手機的正式登入網址。
echo         正式門市手機要使用的網址，需在 24 小時正式電腦
echo         完成外部連線設定後才能確定。
echo.
echo 按 Ctrl+C 可停止服務；或另開視窗執行 scripts\stop_production.bat
echo ----------------------------------------
echo.

python run.py
set "EC=%ERRORLEVEL%"
echo.
echo 服務已結束（exit code %EC%）。
exit /b %EC%
