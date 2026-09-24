# Production Cutover Checklist

**目前正式路線：GitHub Pages + ngrok + 24 小時電腦 FastAPI + SQLite。**  
見 `docs/NgrokProduction.md`、`docs/NgrokSetup.md`、`docs/NgrokE2ETest.md`。

不要建立 Cloud PostgreSQL，不要執行 SQLite → PostgreSQL `--confirm`。

## 現在要做的人工步驟

1. GitHub 建立 repository（名稱若用 `attendance`，Pages 路徑為 `/attendance/`）。不要猜測帳號。
2. 設定 remote 並 push（本地目前分支是 `master`；遠端若用 `main`，可 `git push -u origin master:main`）。
3. Repo → Settings → Pages → Source = GitHub Actions。
4. 24 小時電腦安裝 ngrok、`ngrok config add-authtoken`（token 不進 Git）。
5. 啟動 FastAPI 與 `scripts\start_ngrok.bat`，取得 `https://...`。
6. GitHub Secret `ATTENDANCE_API_BASE` = 該 https 根網址。
7. Secret 設好後再跑 Deploy Pages。ngrok URL 一變就要更新 Secret 並重新 deploy。
8. 24 小時電腦設定 `CORS_ORIGINS=https://<github-account>.github.io`（不要 `*`）與 `APP_ENV=production`。
9. 手機 4G/5G 依 `docs/NgrokE2ETest.md` 測試。

## 備用（不要現在做）

Cloud FastAPI、Cloud PostgreSQL、Alembic 上雲、`migrate_sqlite_to_postgres.py --confirm` 都不是目前 production。相關程式留在 repo 裡，但不要執行。


## Rollback

- 保留 `data\attendance.sqlite3` 與 `D:\出勤打卡系統_phase1_backup`
- 不要刪除正式 SQLite
- ngrok 或 Pages 出問題時，24 小時電腦上的 FastAPI + SQLite 仍是資料來源

## Source of truth

SQLite：`D:\出勤打卡系統\data\attendance.sqlite3`  
不要 SQLite 與 PostgreSQL 雙寫。
