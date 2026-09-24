# Cloud Migration Notes（備用，不是目前正式架構）

**目前正式架構已改為：GitHub Pages + ngrok + 24 小時 Windows FastAPI + SQLite。**  
見 `docs/NgrokProduction.md`。

下面的 Cloud FastAPI / PostgreSQL / Neon / Railway / Render 內容只留作未來備用。  
不要把它當成現在的 production，也不要執行 `migrate_sqlite_to_postgres.py --confirm`。

正式資料庫維持：

```text
D:\出勤打卡系統\data\attendance.sqlite3
```

---

## 以下為先前 Cloud 路線備忘（非現行 production）


| Phase | 狀態 |
|-------|------|
| 1 設定化 | 完成 |
| 2 GitHub Pages 靜態前端 | 程式／workflow 完成；待 GitHub 帳號啟用 Pages |
| 3 Cloud FastAPI | 程式完成（Alembic／PreviewStore／idle／health／PORT） |
| 4 SQLite→PG 工具 | 工具完成；待真實 PostgreSQL 執行 `--confirm` |
| 5–7 正式部署／Cutover | **等待外部帳號與 credentials** |

---

## Target Architecture

```
員工／Admin Browser
        ↓ HTTPS
GitHub Pages (/attendance/)
        ↓ HTTPS + Bearer JWT
Cloud FastAPI
        ↓
Cloud PostgreSQL（唯一正式資料來源）
```

禁止長期雙寫 SQLite + PostgreSQL。  
本機 `data/attendance.sqlite3` 僅開發／備份，**不刪、不上傳公開 Repo**。

---

## Phase 2 — Frontend / Pages

- `scripts/prepare_github_pages.py` → `.pages-dist`
- `.github/workflows/deploy-pages.yml`（push `main`）
- `BASE_PATH=/attendance`、相對路徑 HTML／manifest／SW
- `API_BASE`：開發 `""`；正式由 secret `ATTENDANCE_API_BASE` 注入 `config.runtime.js`
- SW：**不 cache** `/api/*`（network-only）
- 本機仍：`http://127.0.0.1:8800` 與 `/admin`

## Phase 3 — Backend

- 環境變數見 `EnvironmentVariables.md`
- PostgreSQL：`DATABASE_URL=postgresql+psycopg2://...`
- Alembic：`alembic upgrade head`（空庫建 schema）
- `PREVIEW_STORE=memory|postgres`
- Server idle：`token_activities` + `IDLE_TIMEOUT_MINUTES`（節流寫入）
- 啟動：`python scripts/start_cloud.py`（`$PORT`）或 `Procfile`

## Phase 4 — Migration

```bash
python scripts/migrate_sqlite_to_postgres.py --dry-run
python scripts/migrate_sqlite_to_postgres.py --confirm --postgres-url "postgresql+psycopg2://..."
```

僅 `--confirm` 寫入 PG；來源 SQLite **唯讀**、永不刪改。

## Phase 5–7

需人工：GitHub、Cloud provider、PostgreSQL、環境變數、Pages 啟用。  
見 `docs/ProductionCutover.md`。
