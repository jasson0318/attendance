# Production Cutover Checklist

**現況**：程式與工具已 Cloud-ready；正式切換需人工帳號／付款／credentials。  
未完成外部步驟前，**不得**宣告 PRODUCTION READY。

## 人工步驟（明天）

1. 建立／登入 **GitHub** 帳號；建立 repo（建議名 `attendance` 以得到 `/attendance/` 路徑，或調整 Pages base）。
2. 將本專案 push 到 `main`（確認 `.gitignore` 已排除 `.env`／sqlite／secret）。
3. Repo Settings → Pages → Source = **GitHub Actions**；執行 `Deploy GitHub Pages` workflow。
4. 設定 repo secret：`ATTENDANCE_API_BASE` = 正式 Cloud API 根網址（取得後再填）。
5. 選擇 Cloud 主機（如 Railway／Render／Fly 等）並建立帳號／Billing（若需要）。
6. 建立 **Cloud PostgreSQL**；取得 `DATABASE_URL`。
7. 設定 Cloud 環境變數：
   - `APP_ENV=production`
   - `DATABASE_URL=<postgres>`
   - `SECRET_KEY=<強隨機>`
   - `CORS_ORIGINS=https://<github-user>.github.io`
   - `APP_TIMEZONE=Asia/Taipei`
   - `IDLE_TIMEOUT_MINUTES=3`
   - `PREVIEW_STORE=postgres`（多實例）
   - `PORT` 由平台注入
8. 部署 API：`python scripts/start_cloud.py` 或 `Procfile`。
9. `alembic upgrade head`（或首次啟動 create_all）。
10. 遷移資料（來源 SQLite **唯讀、不刪**）：
    ```bash
    python scripts/migrate_sqlite_to_postgres.py --dry-run --postgres-url "..."
    python scripts/migrate_sqlite_to_postgres.py --confirm --postgres-url "..."
    ```
11. 驗證：`/health`、login、打卡流程、Admin、Excel、idle。
12. 更新 Pages `ATTENDANCE_API_BASE` 並重新 deploy。
13. 公司 24h 電腦：只用瀏覽器開 Pages Admin；**不要**對外開 8800／Port Forward／VPN／Tunnel。

## Rollback

- 保留 `data/attendance.sqlite3` 與 `D:\出勤打卡系統_phase1_backup`
- 保留 migration 腳本與先前 Git commit
- Cloud 出問題：**不要刪** production DB；可暫時指回本機開發環境

## Source of truth（正式後）

PostgreSQL only。禁止 SQLite↔PG 雙寫。
