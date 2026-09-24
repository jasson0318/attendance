# 出勤打卡系統（Attendance System）

公司內部員工出勤管理與手機打卡系統（PWA / Mobile Web）。

## 目前正式架構

```
員工 / Admin 瀏覽器
        ↓ HTTPS
GitHub Pages（/attendance/）
        ↓
ngrok HTTPS
        ↓
24 小時 Windows 電腦 FastAPI :8800
        ↓
SQLite  data\attendance.sqlite3
```

本機開發仍然是 `http://127.0.0.1:8800`（`API_BASE` 為空，走同源 `/api`）。

說明：

- [docs/NgrokProduction.md](docs/NgrokProduction.md)
- [docs/NgrokSetup.md](docs/NgrokSetup.md)
- [docs/NgrokE2ETest.md](docs/NgrokE2ETest.md)
- [docs/EnvironmentVariables.md](docs/EnvironmentVariables.md)

Cloud PostgreSQL / Cloud FastAPI 只留在 [docs/CloudMigration.md](docs/CloudMigration.md) 當備用，**不是**現在的 production。不要執行 SQLite → PostgreSQL。

## 環境需求

- Windows
- Python 3.12+
- 正式對外：ngrok（authtoken 存在 ngrok 自己的設定，不進 Git）

## 安裝

```bat
cd /d 專案目錄
scripts\install_requirements.bat
```

或：

```bat
python -m pip install -r requirements.txt
python scripts\generate_icons.py
```

## 啟動

開發／正式皆可：

```bat
scripts\start_production.bat
```

或：

```bat
python run.py
```

停止：

```bat
scripts\stop_production.bat
```

- 綁定：`0.0.0.0:8800`
- 本機開發：`http://127.0.0.1:8800`
- 管理後台（本機）：`http://127.0.0.1:8800/admin`
- 開發環境 API 文件：`http://127.0.0.1:8800/docs`（`APP_ENV=production` 時關閉）

正式手機入口是 GitHub Pages，不是區網 IP。API 位址由 GitHub Secret `ATTENDANCE_API_BASE` 注入（ngrok `https://`）。

## 預設帳號

| 角色 | 帳號 | 密碼 |
|------|------|------|
| 管理員 | admin | admin123 |
| 示範員工 | demo | demo123 |

請登入後立即修改密碼。

## 安全設定

JWT 簽章金鑰：

1. 環境變數 `ATTENDANCE_SECRET_KEY`（優先）
2. 否則自動使用／建立 `data\.secret_key`（已存在則不重建）

**不要**把真正密鑰寫進程式碼、前端或 Git。

## 資料庫

正式資料庫就是 SQLite：`data\attendance.sqlite3`  
不要刪除、不要清空、不要改成 PostgreSQL 雙寫。  
不與其他系統（含 SmartRx）共用。

## 測試

```bat
python -m pytest -q
python scripts\run_validation_checklist.py
```

## 功能摘要

- 員工帳號密碼登入後直接打卡（上班／開始休息／結束休息／下班）
- 嚴格打卡順序；跳過休息／提前下班／無排班需填原因
- 遲到／早退寬限；補打卡與超額警示
- Excel 排班匯入與報表匯出
- 管理員後台；3 分鐘無操作自動登出
- **無** GPS／Wi-Fi／QR／NFC／Beacon 現場驗證
