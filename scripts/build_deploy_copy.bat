@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 從開發專案建立乾淨部署副本 → D:\出勤打卡系統_deploy
REM 不刪除、不修改開發專案內容以外的邏輯；僅複製檔案。

set "SRC=D:\出勤打卡系統"
set "DST=D:\出勤打卡系統_deploy"

if not exist "%SRC%\run.py" (
  echo [錯誤] 找不到開發專案: %SRC%
  exit /b 1
)

echo 來源: %SRC%
echo 目標: %DST%
echo.

if exist "%DST%" (
  echo 清除舊部署副本...
  rmdir /s /q "%DST%"
)

mkdir "%DST%" 2>nul

REM /E 含子目錄；排除開發產物與虛擬環境
robocopy "%SRC%" "%DST%" /E /NFL /NDL /NJH /NJS /nc /ns /np ^
  /XD "__pycache__" ".pytest_cache" ".venv" "venv" "node_modules" ".git" ^
  /XF "*.pyc" "*.pyo" "*.pid" "*.log"

REM 強制排除機敏／正式不應沿用的資料
if exist "%DST%\data\attendance.sqlite3" del /f /q "%DST%\data\attendance.sqlite3"
if exist "%DST%\data\.secret_key" del /f /q "%DST%\data\.secret_key"

REM 確保 data 目錄與 gitkeep
if not exist "%DST%\data" mkdir "%DST%\data"
if not exist "%DST%\data\.gitkeep" type nul > "%DST%\data\.gitkeep"

REM 再清一次可能被複製進來的快取
for /d /r "%DST%" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
if exist "%DST%\.pytest_cache" rd /s /q "%DST%\.pytest_cache"

echo.
echo [完成] 部署副本: %DST%
echo 已排除: attendance.sqlite3, .secret_key, __pycache__, .pytest_cache, .venv
exit /b 0
