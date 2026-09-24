@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 24 小時電腦用：production 模式（關閉 /docs）+ 既有 SQLite。
REM 不刪除、不搬移 data\attendance.sqlite3。
REM CORS_ORIGINS 必須事先設好（GitHub Pages origin），不可為 *。

cd /d "%~dp0.."

if not defined APP_ENV set APP_ENV=production

if not defined CORS_ORIGINS (
  echo [錯誤] 請先設定 CORS_ORIGINS，例如：
  echo   set CORS_ORIGINS=https://^<github-account^>.github.io
  echo 不要使用 *，不要猜測 GitHub 帳號。
  exit /b 1
)

echo %CORS_ORIGINS% | findstr /C:"*" >nul
if not errorlevel 1 (
  echo [錯誤] CORS_ORIGINS 不可包含 *
  exit /b 1
)

echo APP_ENV=%APP_ENV%
echo CORS_ORIGINS=%CORS_ORIGINS%
echo 資料庫維持 data\attendance.sqlite3（本腳本不執行 PostgreSQL migration）
echo.

call "%~dp0start_production.bat"
exit /b %ERRORLEVEL%
