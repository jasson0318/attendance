@echo off
chcp 65001 >nul
setlocal EnableExtensions

REM 明確安裝腳本：只有傳入 INSTALL 才會註冊開機啟動。
REM 不寫入 ngrok authtoken，不修改專案內的秘密，不建立自訂常駐程式。

if /I not "%~1"=="INSTALL" (
  echo 用法: scripts\install_ngrok_service.bat INSTALL
  echo.
  echo 這會註冊：
  echo   1. 工作排程 AttendanceFastAPI  -^> scripts\start_production_pc.bat
  echo   2. ngrok 官方 Windows service（優先）
  echo.
  echo 請先完成 docs\NgrokSetup.md：
  echo   ngrok config add-authtoken 會寫入 ngrok 自己的設定，不是這個專案。
  echo 若官方 service 需要 endpoint，請把 config\ngrok.endpoint.example.yml
  echo 合併進 ngrok 的設定檔（不要把 authtoken 放進 Git）。
  echo.
  echo 本腳本不會自動執行，除非你加上 INSTALL。
  exit /b 1
)

cd /d "%~dp0.."
set "ROOT=%CD%"

where python >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 python。
  exit /b 1
)
where ngrok >nul 2>&1
if errorlevel 1 (
  echo [錯誤] 找不到 ngrok。請先安裝並加入 PATH。
  exit /b 1
)

echo 註冊 FastAPI 開機工作排程 AttendanceFastAPI ...
schtasks /Create /F /TN "AttendanceFastAPI" /SC ONSTART /RL LIMITED /TR "\"%ROOT%\scripts\start_production_pc.bat\""
if errorlevel 1 (
  echo [錯誤] 無法建立工作排程。請用系統管理員身分執行。
  exit /b 1
)

echo 嘗試 ngrok 官方 service install ...
ngrok service install
if errorlevel 1 (
  echo.
  echo [注意] ngrok service install 未成功。
  echo 改以工作排程啟動官方指令：ngrok http 127.0.0.1:8800
  echo （authtoken 仍只存在 ngrok 自己的設定，不寫入此專案。）
  schtasks /Create /F /TN "AttendanceNgrok" /SC ONSTART /RL LIMITED /TR "ngrok http 127.0.0.1:8800"
  if errorlevel 1 (
    echo [錯誤] 無法建立 AttendanceNgrok 工作排程。
    exit /b 1
  )
  echo 已建立工作排程 AttendanceNgrok。
  exit /b 0
)

ngrok service start
echo 已安裝 ngrok 官方 service，並已建立 AttendanceFastAPI。
echo 請確認 ngrok 設定裡的 upstream 是 http://127.0.0.1:8800。
exit /b 0
